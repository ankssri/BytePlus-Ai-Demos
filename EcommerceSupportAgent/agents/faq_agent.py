from .base import Agent
from core import cache, llm


class FAQAgent(Agent):
    name = "faq"

    def handle(self, query: str) -> dict:
        hit = cache.lookup(query)
        if hit:
            self.decision("faq_cache_hit", {"query": query}, {"id": hit["id"]})
            return {"reply": hit["answer"], "source": "cache", "faq_id": hit["id"],
                    "requires_human": False}
        # Fall back to LLM-drafted answer, grounded on the policy doc.
        policy = self.tool("policy", "get_policy_document", {})
        doc = policy.get("document", "")
        sys = ("You are a customer support FAQ agent. Answer ONLY from the provided "
               "policy document. If the answer is not in the policy, say you'll route to a human. "
               "Never invent numbers or timelines.")
        reply = llm.chat(sys, f"POLICY:\n{doc}\n\nQUESTION: {query}")
        self.decision("faq_llm_reply", {"query": query}, {"chars": len(reply)})
        return {"reply": reply, "source": "llm+policy", "requires_human": False}
