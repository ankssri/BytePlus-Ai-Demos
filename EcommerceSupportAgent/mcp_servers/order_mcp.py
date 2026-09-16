from . import _util

NAME = "order"
TOOLS = {
    "get_order": {"description": "Fetch an order by order_id.", "params": {"order_id": "str"}, "side_effect": "read"},
    "list_orders_for_user": {"description": "List orders belonging to a user.", "params": {"user_id": "str"}, "side_effect": "read"},
    "update_order_status": {"description": "Update the status of an order (write).", "params": {"order_id": "str", "status": "str"}, "side_effect": "write"},
}

VALID = {"placed", "in_transit", "delivered", "return_requested", "returned", "refunded", "cancelled"}

def call(tool, params):
    orders = _util.load("orders")
    if tool == "get_order":
        o = orders.get(params.get("order_id", ""))
        return {"ok": bool(o), "order": o} if o else {"ok": False, "error": "order not found"}
    if tool == "list_orders_for_user":
        uid = params.get("user_id")
        matches = [o for o in orders.values() if o["user_id"] == uid]
        return {"ok": True, "orders": matches}
    if tool == "update_order_status":
        oid, new = params.get("order_id"), params.get("status")
        if new not in VALID:
            return {"ok": False, "error": f"invalid status '{new}'"}
        if oid not in orders:
            return {"ok": False, "error": "order not found"}
        prev = orders[oid]["status"]
        orders[oid]["status"] = new
        _util.save("orders", orders)
        return {"ok": True, "order_id": oid, "previous": prev, "status": new}
    return {"ok": False, "error": "unknown tool"}
