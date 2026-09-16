"""End-to-end return + refund agent.

Workflow:
  1. Extract order id.
  2. Fetch order, user, product (reversible / read).
  3. Ask policy MCP: eligible? auto-approve?
  4. If auto-approve -> mark order return_requested (write),
     create return label (write),
     refund payment (write, idempotent),
     mark order refunded (write),
     reply to customer.
  5. If not auto-approve -> stop at 'awaiting_human' and return proposed
     action for a human reviewer to approve via /human/approve.
"""
from __future__ import annotations
import re
from .base import Agent
from core import idempotency, audit


class ReturnRefundAgent(Agent):
    name = "return_refund"

    def handle(self, query: str, order_id: str | None, *, human_approved: bool = False) -> dict:
        oid = order_id or self._extract_order_id(query)
        if not oid:
            return {"reply": "Please share the order ID you'd like to return (e.g. O5003).",
                    "requires_human": False}

        order_res = self.tool("order", "get_order", {"order_id": oid})
        if not order_res.get("ok"):
            return {"reply": f"I couldn't find order **{oid}**.", "requires_human": False}
        o = order_res["order"]

        user_res = self.tool("user", "get_user", {"user_id": o["user_id"]})
        prod_res = self.tool("product", "get_product", {"product_id": o["product_id"]})
        pay_res  = self.tool("payment", "get_payment_for_order", {"order_id": oid})

        elig = self.tool("policy", "check_return_eligibility", {"order_id": oid})
        if not elig.get("ok"):
            return {"reply": "Policy check failed. Escalating to a human agent.",
                    "requires_human": True}

        if not elig["eligible"]:
            reasons = "; ".join(elig["blockers"])
            self.decision("policy_deny", {"order_id": oid}, elig, ok=True)
            return {
                "reply": (f"I'm sorry — order **{oid}** isn't eligible for return under our policy: "
                          f"{reasons}. If you'd like, I can escalate to a human agent for a courtesy review."),
                "requires_human": True,
                "eligibility": elig,
            }

        auto_ok = elig["auto_approve"]
        if not auto_ok and not human_approved:
            self.decision("await_human_approval", {"order_id": oid}, elig, ok=True)
            return {
                "reply": (f"Order **{oid}** is eligible for return, but requires human approval "
                          f"(reasons: {'; '.join(elig['reasons']) or 'policy-driven review'}). "
                          f"I've queued it for a human agent."),
                "requires_human": True,
                "awaiting_human": True,
                "proposed_action": {
                    "order_id": oid,
                    "refund_amount": o["amount"],
                    "payment_id": pay_res.get("payment", {}).get("payment_id"),
                },
                "eligibility": elig,
            }

        # ---- Execute irreversible writes, all idempotent ----------------
        pay_id = pay_res["payment"]["payment_id"]
        amount = o["amount"]

        upd1 = self.tool("order", "update_order_status",
                         {"order_id": oid, "status": "return_requested"},
                         idempotency_key=idempotency.make_key(self.case_id, "req", oid))

        label = idempotency.run_once(
            idempotency.make_key(self.case_id, "label", oid),
            self.case_id,
            lambda: self.tool("shipping", "create_return_label",
                              {"order_id": oid, "idempotency_key": f"{self.case_id}:{oid}"}),
        )

        refund_key = idempotency.make_key(self.case_id, "refund", pay_id, amount)
        refund = idempotency.run_once(
            refund_key, self.case_id,
            lambda: self.tool("payment", "refund_payment",
                              {"payment_id": pay_id, "amount": amount,
                               "idempotency_key": refund_key},
                              idempotency_key=refund_key),
        )

        upd2 = self.tool("order", "update_order_status",
                         {"order_id": oid, "status": "refunded"},
                         idempotency_key=idempotency.make_key(self.case_id, "done", oid))

        approved_by = "human agent" if human_approved else "auto-approval (policy match)"
        reply = (
            f"Done. Return + refund processed for order **{oid}** ({approved_by}).\n"
            f"- Return label: `{label.get('return_label','-')}` via {label.get('carrier','-')}\n"
            f"- Refund: **${amount:.2f}** to original payment `{pay_id}` "
            f"(5–7 business days to appear).\n"
            f"- New order status: **{upd2.get('status','refunded')}**."
        )
        self.decision("return_refund_complete",
                      {"order_id": oid, "amount": amount},
                      {"label": label, "refund": refund}, ok=True)
        return {
            "reply": reply, "requires_human": False,
            "actions": {"status_update": upd1, "label": label, "refund": refund,
                        "final_status": upd2},
        }

    @staticmethod
    def _extract_order_id(text: str) -> str | None:
        m = re.search(r"\bO\d{4,6}\b", text.upper())
        return m.group(0) if m else None
