from backend.app.models import Product, Review
from backend.app.services.prompts import SYSTEM_PROMPT

INJECTION_MARKERS = ("ignore previous", "system prompt", "developer message", "jailbreak")
class AIOrchestrator:
    def needs_clarification(self, message: str) -> str | None:
        m = message.lower()
        if any(x in m for x in INJECTION_MARKERS): return "What product category are you shopping for?"
        if len(m.split()) < 3: return "What is your budget?"
        return None
    def answer(self, message: str, products: list[Product]) -> str:
        if not products: return "I could not find matching catalog products. Can you share a category, brand, or budget?"
        names = ", ".join(p.name for p in products[:3])
        return f"Based on the catalog and your request, I recommend considering: {names}. {SYSTEM_PROMPT}"
    def summarize_reviews(self, reviews: list[Review]) -> dict:
        positives = [r.title for r in reviews if r.rating >= 4]
        negatives = [r.title for r in reviews if r.rating < 4]
        avg = sum(r.rating for r in reviews) / len(reviews) if reviews else 0
        return {"pros": positives[:5], "cons": negatives[:5], "overall_opinion": f"Average rating {avg:.1f} from {len(reviews)} reviews.", "sentiment": "positive" if avg >= 4 else "mixed" if avg >= 3 else "negative"}
    def compare(self, products: list[Product]) -> dict:
        winner = max(products, key=lambda p: (p.rating, -p.price)) if products else None
        return {"products": products, "winner": winner.name if winner else None, "recommendation": f"Choose {winner.name} for the best rating-to-price balance." if winner else "No products found."}
