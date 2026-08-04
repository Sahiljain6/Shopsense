from openai import OpenAI
from pinecone import Pinecone
from backend.app.core.config import get_settings
from backend.app.models import Product, Review
from backend.app.services.prompts import SYSTEM_PROMPT

INJECTION_MARKERS = ("ignore previous", "system prompt", "developer message", "jailbreak")
class AIOrchestrator:
    def __init__(self):
        self.settings=get_settings(); self.client=OpenAI(api_key=self.settings.openai_api_key) if self.settings.openai_api_key else None
    def embed(self, text: str) -> list[float]:
        if self.client:
            return self.client.embeddings.create(model=self.settings.embedding_model, input=text).data[0].embedding
        return [float((sum(map(ord, text[i::64])) % 997) / 997) for i in range(64)]
    def vector_context(self, message: str, products: list[Product]) -> str:
        if self.settings.pinecone_api_key:
            try:
                pc=Pinecone(api_key=self.settings.pinecone_api_key); idx=pc.Index(self.settings.pinecone_index)
                res=idx.query(vector=self.embed(message), top_k=5, include_metadata=True)
                return "\n".join(str(m.get("metadata",{})) for m in res.get("matches",[]))
            except Exception:
                pass
        return "\n".join(f"{p.name}: {p.description} ${p.price} rating {p.rating}" for p in products[:5])
    def _complete(self, prompt: str) -> str:
        if self.client:
            r=self.client.chat.completions.create(model=self.settings.openai_model, messages=[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":prompt}])
            return r.choices[0].message.content or ""
        return ""
    def needs_clarification(self, message: str) -> str|None:
        m=message.lower()
        if any(x in m for x in INJECTION_MARKERS): return "What product category are you shopping for?"
        if len(m.split())<3: return "What is your budget and primary use case?"
        if not any(ch.isdigit() for ch in m) and not any(w in m for w in ("cheap","premium","budget","best")): return "Do you have a budget range or preferred brand?"
        return None
    def answer(self, message: str, products: list[Product], memory: list[str]|None=None) -> str:
        if not products: return "I could not find matching catalog products. Share a category, brand, feature, or budget and I will narrow it down."
        context=self.vector_context(message, products); prompt=f"User: {message}\nMemory: {memory or []}\nCatalog context:\n{context}\nGive concise recommendations with reasons."
        ai=self._complete(prompt)
        return ai or f"I recommend {', '.join(p.name for p in products[:3])}. They best match your request by rating, stock, and catalog relevance."
    def summarize_reviews(self, reviews: list[Review]) -> dict:
        avg=sum(r.rating for r in reviews)/len(reviews) if reviews else 0; pros=[r.title for r in reviews if r.rating>=4][:5]; cons=[r.title for r in reviews if r.rating<4][:5]
        return {"pros":pros,"cons":cons,"overall_opinion":f"Average rating {avg:.1f} from {len(reviews)} reviews.","sentiment":"positive" if avg>=4 else "mixed" if avg>=3 else "negative"}
    def compare(self, products: list[Product]) -> dict:
        rows=[{"id":p.id,"name":p.name,"brand":p.brand,"price":p.price,"rating":p.rating,"stock":p.stock,"strength":p.description[:120]} for p in products]
        winner=max(products,key=lambda p:(p.rating,-p.price)) if products else None
        return {"products":rows,"winner":winner.name if winner else None,"recommendation":f"Choose {winner.name} for the strongest rating-to-price balance." if winner else "No products found."}
