from . import _util

NAME = "shipping"
TOOLS = {
    "get_shipment": {"description": "Get shipping/tracking info for an order.", "params": {"order_id": "str"}, "side_effect": "read"},
    "create_return_label": {"description": "Issue a return shipping label (write).", "params": {"order_id": "str", "idempotency_key": "str"}, "side_effect": "write"},
}

def call(tool, params):
    ships = _util.load("shipping")
    if tool == "get_shipment":
        s = ships.get(params.get("order_id", ""))
        return {"ok": bool(s), "shipment": s} if s else {"ok": False, "error": "shipment not found"}
    if tool == "create_return_label":
        oid = params.get("order_id")
        if oid not in ships:
            return {"ok": False, "error": "shipment not found"}
        s = ships[oid]
        label = f"RET-{s['tracking']}"
        return {"ok": True, "order_id": oid, "return_label": label, "carrier": s["carrier"]}
    return {"ok": False, "error": "unknown tool"}
