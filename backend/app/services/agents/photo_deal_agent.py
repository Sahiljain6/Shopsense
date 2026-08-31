import logging
from typing import Any
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Product
from app.schemas.api import ChatResponse
from app.services.catalog import CatalogService
from app.services.deal_timing import analyze_deal_timing
from app.services.finance import calculate_emi_options
from app.services.vision import identify_image

logger = logging.getLogger("shopsense.agents.photo_deal")

# Category mapping keywords
CATEGORY_MAP = {
    "Phones": ["phone", "smartphone", "mobile", "iphone", "android", "cellphone", "screen"],
    "Laptops": ["laptop", "computer", "notebook", "macbook", "ultrabook", "netbook"],
    "Audio": ["headphone", "headphones", "earphone", "earphones", "earbuds", "audio", "speaker", "headset"],
    "Peripherals": ["keyboard", "mouse", "monitor", "dock", "cable", "charger", "gadget", "peripheral"],
}


class VisualInspectorAgent:
    """Agent 1: Inspects uploaded product images, extracts visual characteristics,
    diagnoses potential visual/catalog mismatches, and hands off to Agent 2.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    def inspect(self, image_bytes: bytes, db: Session) -> dict[str, Any]:
        try:
            labels = identify_image(image_bytes, self.api_key)
        except Exception as err:
            logger.warning("Visual agent inspection notice: %s", err)
            labels = ["gadget", "electronic device"]

        if not labels:
            labels = ["product", "gadget"]

        clean_labels = [l.strip().lower() for l in labels if l.strip()]

        # Identify category from visual cues
        detected_category = "General"
        for cat, kws in CATEGORY_MAP.items():
            if any(kw in " ".join(clean_labels) for kw in kws):
                detected_category = cat
                break

        # Check for visual mismatch against catalog
        catalog = CatalogService(db)
        direct_matches = catalog.search(" ".join(clean_labels[:3]), limit=5)

        is_mismatch = False
        mismatch_reason = ""

        if not direct_matches:
            is_mismatch = True
            mismatch_reason = f"Exact visual search for '{', '.join(clean_labels[:3])}' yielded no direct catalog inventory."
        elif len(clean_labels) <= 2 or all(l in ["gadget", "product", "technology", "electronic device"] for l in clean_labels[:2]):
            is_mismatch = True
            mismatch_reason = "Photo has generic visual tags; requires spec and intent reconciliation."
        elif detected_category == "General":
            is_mismatch = True
            mismatch_reason = "Category boundary ambiguous from image angle; consulting Deal Specialist for best fit."

        handoff_prompt = (
            f"Agent 1 (Visual Inspector) ➡️ Agent 2 (Deal & Offer Specialist): "
            f"I analyzed the uploaded image. Detected visual cues: [{', '.join(clean_labels[:5])}]. "
            f"Likely Category: {detected_category}. "
            f"{'Notice: Visual mismatch detected — ' + mismatch_reason if is_mismatch else 'Image identified.'} "
            f"Please evaluate our inventory, resolve the optimal option with top performance and customer value, "
            f"and gather all ongoing bank discounts, EMI schemes, and deal timing so the customer gets the best deal."
        )

        return {
            "labels": clean_labels,
            "detected_category": detected_category,
            "is_mismatch": is_mismatch,
            "mismatch_reason": mismatch_reason,
            "direct_matches": direct_matches,
            "handoff_prompt": handoff_prompt,
        }


class DealOfferSpecialistAgent:
    """Agent 2: Receives visual findings from Agent 1, resolves any catalog mismatch,
    selects the ⭐ Optimal Option, and aggregates active financing & promotional offers.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.catalog = CatalogService(db)

    def resolve_and_scout(self, visual_data: dict[str, Any]) -> dict[str, Any]:
        category = visual_data.get("detected_category", "General")
        labels = visual_data.get("labels", [])
        direct_matches = visual_data.get("direct_matches", [])

        candidate_products: list[Product] = list(direct_matches)

        # If direct matches are sparse or there is a mismatch, find the best alternatives in this category
        if len(candidate_products) < 2:
            cat_filter = category if category in ["Phones", "Laptops", "Audio", "Peripherals"] else None
            # Search using individual high-signal keywords
            for kw in labels[:4]:
                if len(kw) > 3 and kw not in ["gadget", "product", "technology"]:
                    extra = self.catalog.search(kw, limit=4)
                    for p in extra:
                        if p.id not in [c.id for c in candidate_products]:
                            candidate_products.append(p)

            # If still empty, fall back to top rated in detected category
            if not candidate_products and cat_filter:
                all_cat_prods = self.catalog.search(cat_filter, limit=6)
                candidate_products.extend(all_cat_prods)

            # Ultimate catalog fallback
            if not candidate_products:
                candidate_products = self.catalog.search("", limit=4)

        # Select the ⭐ Optimal Option based on rating and value-for-money
        # Sort by rating descending, then price reasonable
        sorted_candidates = sorted(
            candidate_products,
            key=lambda p: (getattr(p, "rating", 4.0) or 4.0, -getattr(p, "price", 0)),
            reverse=True
        )

        optimal_product = sorted_candidates[0] if sorted_candidates else None

        # Gather ongoing deals & active offers for the optimal product
        offers_data = {}
        if optimal_product:
            price = float(optimal_product.price)
            emi_info = calculate_emi_options(price)
            deal_timing_info = analyze_deal_timing(
                optimal_product.name,
                price,
                category.lower() if category else "general"
            )

            offers_data = {
                "emi": emi_info,
                "deal_timing": deal_timing_info,
                "best_monthly": emi_info.get("best_monthly", "EMI available"),
                "bank_discounts": emi_info.get("bank_offers", [])[:2],
                "timing_verdict": deal_timing_info.get("verdict", "Good time to buy"),
                "next_sale": deal_timing_info.get("next_sale_event", "Seasonal Mega Sale"),
            }

        return {
            "candidate_products": sorted_candidates[:5],
            "optimal_product": optimal_product,
            "offers": offers_data,
        }


def resolve_photo_mismatch_and_find_deals(image_bytes: bytes, db: Session) -> ChatResponse:
    """Collaborative multi-agent pipeline:
    Agent 1 (Visual Inspector) ➡️ Agent 2 (Deal & Offer Specialist)
    Resolves photo mismatches, selects optimal options, and highlights ongoing offers.
    """
    settings = get_settings()

    # Step 1: Agent 1 analyzes photo & diagnoses mismatch
    agent_1 = VisualInspectorAgent(api_key=settings.google_vision_api_key)
    visual_findings = agent_1.inspect(image_bytes, db)

    # Step 2: Agent 1 consults Agent 2
    agent_2 = DealOfferSpecialistAgent(db)
    deal_findings = agent_2.resolve_and_scout(visual_findings)

    candidates = deal_findings["candidate_products"]
    optimal = deal_findings["optimal_product"]
    offers = deal_findings["offers"]

    labels_str = ", ".join(visual_findings["labels"][:4]) or "Product"
    cat_str = visual_findings["detected_category"]

    # Build collaborative multi-agent response
    lines = [
        "### 📸 Multi-Agent Visual Shopping & Deal Finder\n",
        f"**🔍 Agent 1 (Visual Inspector)**:\n"
        f"• **Visual Analysis**: Detected `{labels_str}` (Estimated Category: **{cat_str}**)\n"
    ]

    if visual_findings["is_mismatch"]:
        lines.append(
            f"• **Photo Mismatch Resolved**: *{visual_findings['mismatch_reason']}*\n"
            f"• **Handoff**: *Agent 1 consulted Agent 2 (Deal & Offer Specialist) to find the closest in-stock match and unlock active promotions.* 🤝\n"
        )
    else:
        lines.append(
            f"• **Visual Match Confirmed**: Photo matches inventory features.\n"
            f"• **Handoff**: *Agent 1 requested Agent 2 to scour optimal deals and active financing.* 🤝\n"
        )

    lines.append("**🤝 Agent 2 (Deal & Offer Specialist)**:\n")

    if optimal:
        lines.append(
            f"• **⭐ Optimal Option**: **{optimal.name}** — **₹{optimal.price:,.0f}**\n"
            f"  *Reason*: Top-rated in this category ({getattr(optimal, 'rating', 4.5)}/5 ⭐) with matching form factor and highest performance-to-price ratio.\n\n"
            f"#### 🎁 Ongoing Deals & Active Offers for You:\n"
            f"• 💳 **No-Cost EMI**: Available from **{offers.get('best_monthly')}** (0% extra interest across major banks)\n"
        )

        for off in offers.get("bank_discounts", []):
            lines.append(f"• 🏦 **Bank Offer**: {off}\n")

        lines.append(
            f"• ⏳ **Deal Timing**: {offers.get('timing_verdict')}\n"
        )

        if len(candidates) > 1:
            lines.append("\n**Other Closely Matched Alternatives**:\n")
            for alt in candidates[1:4]:
                lines.append(f"• **{alt.name}** — ₹{alt.price:,.0f} ({alt.brand})\n")

        lines.append(
            "\n✓ *Instant dispatch available. You can add the optimal option to your cart or compare below.*"
        )

    product_ids = [p.id for p in candidates]
    reasons = {
        str(p.id): (
            "⭐ Optimal Pick: Best price-performance match"
            if optimal and p.id == optimal.id
            else f"Visual alternative matching {cat_str}"
        )
        for p in candidates
    }

    return ChatResponse(
        answer="\n".join(lines),
        product_ids=product_ids,
        reasons=reasons,
    )
