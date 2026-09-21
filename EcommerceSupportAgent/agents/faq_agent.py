from .base import Agent
from core import cache, llm, jev_ai


class FAQAgent(Agent):
    name = "faq"

    def handle(self, query: str) -> dict:
        # 1. Regex cache (fast path).
        hit = cache.lookup(query)
        if hit:
            self.decision("faq_cache_hit", {"query": query, "router": "regex"},
                          {"id": hit["id"]})
            return {"reply": hit["answer"], "source": "cache", "faq_id": hit["id"],
                    "requires_human": False}

        # 2. Semantic router via Jev (typed judgment). Still a cache hit -
        # no LLM, no downstream call, just a typed lookup into the same
        # canned answers.
        try:
            d = jev_ai.match_faq(query)
            if d.faq_id != "none":
                for item in cache.FAQ:
                    if item["id"] == d.faq_id:
                        self.decision("faq_cache_hit",
                                      {"query": query, "router": "jev"},
                                      {"id": item["id"]})
                        return {"reply": item["answer"], "source": "cache+jev",
                                "faq_id": item["id"], "requires_human": False}
        except jev_ai.NotAvailable:
            pass
        except Exception:
            pass  # any Jev/network error - fall through to LLM

        # 3. LLM-drafted answer grounded on the policy doc.
        policy = self.tool("policy", "get_policy_document", {})
        doc = policy.get("document", "")
        sys = ("You are a customer support FAQ agent. Answer ONLY from the provided "
               "policy document. If the answer is not in the policy, say you'll route to a human. "
               "Never invent numbers or timelines.")
        reply = llm.chat(sys, f"POLICY:\n{doc}\n\nQUESTION: {query}")
        self.decision("faq_llm_reply", {"query": query}, {"chars": len(reply)})
        return {"reply": reply, "source": "llm+policy", "requires_human": False}
