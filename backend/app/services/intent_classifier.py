"""Deterministic intent taxonomy for ShopSense shopping requests.

This module deliberately does not call an LLM. It provides a small, testable
classification layer that later orchestration stages can consume without
changing the public chat API.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence


class ShoppingIntent(str, Enum):
    PRODUCT_RECOMMENDATION = "product_recommendation"
    PRODUCT_COMPARISON = "product_comparison"
    DEAL_SEARCH = "deal_search"
    PRODUCT_REVIEW_SUMMARY = "product_review_summary"
    FINANCE_OR_EMI = "finance_or_emi"
    GIFT_RECOMMENDATION = "gift_recommendation"
    DELIVERY_OR_LOGISTICS = "delivery_or_logistics"
    PRODUCT_INFORMATION = "product_information"
    GENERAL_SHOPPING_QUERY = "general_shopping_query"
    CLARIFICATION_REQUIRED = "clarification_required"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class IntentResult:
    """Internal classification result; not a public API response."""

    intent: ShoppingIntent
    secondary_intents: tuple[ShoppingIntent, ...] = ()
    reason: str = ""


INTENT_DESCRIPTIONS: Mapping[ShoppingIntent, str] = {
    ShoppingIntent.PRODUCT_RECOMMENDATION: "Recommend products based on stated needs and constraints.",
    ShoppingIntent.PRODUCT_COMPARISON: "Compare two or more identifiable products or alternatives.",
    ShoppingIntent.DEAL_SEARCH: "Find or evaluate discounts, deals, offers, or price drops.",
    ShoppingIntent.PRODUCT_REVIEW_SUMMARY: "Summarize or evaluate product reviews and sentiment.",
    ShoppingIntent.FINANCE_OR_EMI: "Answer shopping finance questions, including EMI and total cost.",
    ShoppingIntent.GIFT_RECOMMENDATION: "Recommend gifts based on recipient, occasion, interests, and budget.",
    ShoppingIntent.DELIVERY_OR_LOGISTICS: "Answer delivery, shipping, arrival, or PIN-code questions.",
    ShoppingIntent.PRODUCT_INFORMATION: "Explain product specifications, features, or compatibility.",
    ShoppingIntent.GENERAL_SHOPPING_QUERY: "Answer general buying advice and shopping education questions.",
    ShoppingIntent.CLARIFICATION_REQUIRED: "The request is too ambiguous to act on safely.",
    ShoppingIntent.OUT_OF_SCOPE: "The request is unrelated to the shopping assistant's supported scope.",
}


_WORD = r"\b"
_PATTERNS: dict[str, re.Pattern[str]] = {
    "gift": re.compile(r"\b(gift|gifts|birthday|anniversary|raksha ?bandhan|present for|for my (?:friend|mother|father|sister|brother|partner|wife|husband))\b", re.I),
    "finance": re.compile(r"\b(emi|equated monthly installment|monthly instalment|monthly installment|installments?|instalments?|interest rate|annual interest|down payment|total repayment|total payable|affordability|finance options?|loan cost|calculate.{0,20}\bpayment)\b", re.I),
    "delivery": re.compile(r"\b(deliver(?:y|ed|able)?|shipping|ship to|arrival date|arrive|dispatch|pincode|pin code|postal code|tracking my order|where is my order)\b", re.I),
    "review": re.compile(r"\b(review|reviews|reviewers|ratings?|sentiment|pros and cons|complaints?|customer feedback|worth buying based on)\b", re.I),
    "deal": re.compile(r"\b(deal|deals|discount|discounts|offer|offers|coupon|promo code|price drop|on sale|sale price|best price|cashback|save money)\b", re.I),
    "compare": re.compile(r"\b(compare|comparison|versus|\bvs\.?\b|which is better|difference between|cheaper overall|side.by.side)\b", re.I),
    "recommend": re.compile(r"\b(recommend|recommendation|recommendations|suggest|suggestion|suggestions|which .* should i buy|what should i buy|best .* for|find me|show me .* under|looking for|gift ideas)\b", re.I),
    "product_info": re.compile(r"\b(specifications?|features?|compatib(?:le|ility)|supports?|support for|battery life|processor|ram|storage|dimensions|warranty|what does .* have|tell me about this product)\b", re.I),
    "ambiguous": re.compile(r"^(?:which one is best|what about it|compare it with that one|find the best one|calculate the payment|is it good|what about that|and this one)\??$", re.I),
    "shopping_context": re.compile(r"\b(shop|shopping|buy|buying|purchase|product|products|laptop|phone|smartphone|headphones|earbuds|monitor|chair|camera|keyboard|mouse|price|budget|brand|oled|lcd|gift|catalog|store|retailer|e-?commerce)\b", re.I),
    "out_of_scope": re.compile(r"\b(write (?:a |an )?(?:program|script|essay|poem|story)|debug (?:this|my|the) code|reverse a linked list|solve (?:this )?(?:equation|derivative)|history of ancient rome|homework|generate python code|build a website)\b", re.I),
    "coding": re.compile(r"\b(?:write|generate|create|build|debug|fix|refactor)\b.{0,45}\b(?:code|python|javascript|typescript|program|script|algorithm|api|backend|frontend|function|component)\b", re.I),
}


def _history_text(history: Sequence[Mapping[str, object]] | None) -> str:
    """Flatten recent turns for lightweight follow-up resolution."""
    if not history:
        return ""
    pieces: list[str] = []
    for turn in history[-6:]:
        content = turn.get("content")
        if isinstance(content, str) and content.strip():
            pieces.append(content.strip())
    return " ".join(pieces)


def classify_intent(
    message: str,
    history: Sequence[Mapping[str, object]] | None = None,
) -> IntentResult:
    """Classify a shopping request using ordered, deterministic rules.

    The classifier is intentionally conservative and does not claim that
    live data was searched. History is used only as context for vague
    follow-ups; it does not override a clearly stated current intent.
    """
    current = (message or "").strip()
    if not current:
        return IntentResult(
            ShoppingIntent.CLARIFICATION_REQUIRED,
            reason="No user message was provided.",
        )

    lowered = current.lower()
    context = _history_text(history)
    combined = f"{context} {current}".strip()
    has_context = bool(context)

    # Explicitly out-of-scope requests take priority, except commerce-specific
    # terms such as coupon code, postal code, PIN code, and product code.
    commerce_code_exception = re.search(
        r"\b(coupon|promo|discount|voucher|postal|pin|pincode|product|sku|gift card|referral) code\b",
        lowered,
    )
    if not commerce_code_exception and (
        _PATTERNS["out_of_scope"].search(lowered)
        or _PATTERNS["coding"].search(lowered)
    ):
        return IntentResult(
            ShoppingIntent.OUT_OF_SCOPE,
            reason="The request explicitly asks for a non-shopping task.",
        )

    if _PATTERNS["ambiguous"].match(lowered) and not has_context:
        return IntentResult(
            ShoppingIntent.CLARIFICATION_REQUIRED,
            reason="The request refers to an unidentified item or missing information.",
        )

    primary: ShoppingIntent | None = None
    reason = ""

    # More specific intents precede broader intents to reduce keyword collisions.
    if _PATTERNS["gift"].search(lowered) or re.search(r"\bgift ideas?\b", lowered):
        primary = ShoppingIntent.GIFT_RECOMMENDATION
        reason = "The primary objective is choosing a gift."
    elif _PATTERNS["finance"].search(lowered):
        primary = ShoppingIntent.FINANCE_OR_EMI
        reason = "The request concerns installments, interest, affordability, or payment totals."
    elif _PATTERNS["delivery"].search(lowered):
        primary = ShoppingIntent.DELIVERY_OR_LOGISTICS
        reason = "The request concerns delivery or shipping."
    elif _PATTERNS["review"].search(lowered):
        primary = ShoppingIntent.PRODUCT_REVIEW_SUMMARY
        reason = "The request asks about reviews, ratings, feedback, or sentiment."
    elif _PATTERNS["deal"].search(lowered):
        primary = ShoppingIntent.DEAL_SEARCH
        reason = "The request asks for offers, discounts, or price-saving opportunities."
    elif _PATTERNS["compare"].search(lowered):
        primary = ShoppingIntent.PRODUCT_COMPARISON
        reason = "The request explicitly asks to compare alternatives."
    elif _PATTERNS["recommend"].search(lowered):
        primary = ShoppingIntent.PRODUCT_RECOMMENDATION
        reason = "The request asks for product suggestions or buying choices."
    elif _PATTERNS["product_info"].search(lowered):
        primary = ShoppingIntent.PRODUCT_INFORMATION
        reason = "The request asks for product facts or specifications."
    elif _PATTERNS["shopping_context"].search(lowered):
        primary = ShoppingIntent.GENERAL_SHOPPING_QUERY
        reason = "The request is shopping-related but does not match a more specific intent."
    elif has_context and re.search(r"\b(it|that|this|they|them|same|another|what about|and the)\b", lowered):
        # Follow-ups such as "what about battery?" need context from the previous turn.
        if _PATTERNS["compare"].search(combined):
            primary = ShoppingIntent.PRODUCT_COMPARISON
            reason = "The follow-up refers to an existing comparison in conversation history."
        elif _PATTERNS["recommend"].search(combined) or _PATTERNS["gift"].search(combined):
            primary = ShoppingIntent.PRODUCT_RECOMMENDATION
            reason = "The follow-up depends on a previously discussed shopping request."
        else:
            primary = ShoppingIntent.PRODUCT_INFORMATION
            reason = "The follow-up appears to ask for more information about the current product."
    else:
        return IntentResult(
            ShoppingIntent.OUT_OF_SCOPE,
            reason="No supported shopping intent or shopping context was identified.",
        )

    secondary: list[ShoppingIntent] = []
    if primary != ShoppingIntent.PRODUCT_COMPARISON and _PATTERNS["compare"].search(lowered):
        secondary.append(ShoppingIntent.PRODUCT_COMPARISON)
    if primary != ShoppingIntent.FINANCE_OR_EMI and _PATTERNS["finance"].search(lowered):
        secondary.append(ShoppingIntent.FINANCE_OR_EMI)
    if primary != ShoppingIntent.DEAL_SEARCH and _PATTERNS["deal"].search(lowered):
        secondary.append(ShoppingIntent.DEAL_SEARCH)
    if primary != ShoppingIntent.PRODUCT_REVIEW_SUMMARY and _PATTERNS["review"].search(lowered):
        secondary.append(ShoppingIntent.PRODUCT_REVIEW_SUMMARY)

    return IntentResult(
        intent=primary,
        secondary_intents=tuple(dict.fromkeys(secondary)),
        reason=reason,
    )
