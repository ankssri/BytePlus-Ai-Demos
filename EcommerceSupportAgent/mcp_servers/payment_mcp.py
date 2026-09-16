from . import _util

NAME = "payment"
TOOLS = {
    "get_payment_for_order": {"description": "Fetch payment for an order.", "params": {"order_id": "str"}, "side_effect": "read"},
    "refund_payment": {
        "description": "Refund (part of) a captured payment. Requires idempotency_key.",
        "params": {"payment_id": "str", "amount": "float", "idempotency_key": "str"},
        "side_effect": "write",
    },
}

def call(tool, params):
    payments = _util.load("payments")
    if tool == "get_payment_for_order":
        oid = params.get("order_id")
        for p in payments.values():
            if p["order_id"] == oid:
                return {"ok": True, "payment": p}
        return {"ok": False, "error": "payment not found"}
    if tool == "refund_payment":
        pid = params.get("payment_id")
        amt = float(params.get("amount", 0))
        if pid not in payments:
            return {"ok": False, "error": "payment not found"}
        pay = payments[pid]
        if not pay["captured"]:
            return {"ok": False, "error": "payment not captured"}
        remaining = pay["amount"] - pay["refunded"]
        if amt <= 0 or amt > remaining + 1e-6:
            return {"ok": False, "error": f"invalid refund amount (remaining={remaining:.2f})"}
        # Idempotency is enforced by the core layer (idempotency.py). This
        # tool simply records that the refund happened.
        pay["refunded"] = round(pay["refunded"] + amt, 2)
        _util.save("payments", payments)
        return {"ok": True, "payment_id": pid, "refunded_now": amt, "refunded_total": pay["refunded"]}
    return {"ok": False, "error": "unknown tool"}
