from . import _util

NAME = "policy"
TOOLS = {
    "get_policy_document": {"description": "Return the full store policy markdown.", "params": {}, "side_effect": "read"},
    "check_return_eligibility": {
        "description": "Structured policy check: given order+product+user, decide auto-approve vs human.",
        "params": {"order_id": "str"},
        "side_effect": "read",
    },
}

from datetime import date

def call(tool, params):
    if tool == "get_policy_document":
        return {"ok": True, "document": _util.load_text("policies.md")}

    if tool == "check_return_eligibility":
        oid = params.get("order_id")
        orders = _util.load("orders")
        products = _util.load("products")
        users = _util.load("users")
        if oid not in orders:
            return {"ok": False, "error": "order not found"}
        o = orders[oid]
        p = products[o["product_id"]]
        u = users[o["user_id"]]
        reasons, blockers = [], []

        if o["status"] != "delivered":
            blockers.append(f"order status is '{o['status']}', not 'delivered'")
        if p["final_sale"]:
            blockers.append("product is final sale / clearance")

        days = None
        if o.get("delivered"):
            try:
                d = date.fromisoformat(o["delivered"])
                days = (date.fromisoformat("2026-09-16") - d).days  # frozen 'today' for demo
                if days > p["return_window_days"]:
                    blockers.append(f"outside return window ({days}d > {p['return_window_days']}d)")
                else:
                    reasons.append(f"within return window ({days}d <= {p['return_window_days']}d)")
            except Exception:
                blockers.append("could not parse delivered date")

        auto_ok = (
            not blockers
            and o["amount"] <= 250
            and (u["tier"] in ("gold", "silver") or u["verified"])
        )
        if o["amount"] > 250:
            reasons.append("amount > $250 - requires human")
        if u["tier"] not in ("gold", "silver") and not u["verified"]:
            reasons.append("unverified standard-tier - requires human")

        return {
            "ok": True,
            "eligible": not blockers,
            "auto_approve": bool(auto_ok),
            "blockers": blockers,
            "reasons": reasons,
            "days_since_delivery": days,
            "order": o, "product": p, "user_tier": u["tier"],
        }
    return {"ok": False, "error": "unknown tool"}
