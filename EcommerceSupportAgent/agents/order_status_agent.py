from .base import Agent
import re


class OrderStatusAgent(Agent):
    """Read-only (reversible) agent: fetches order + shipment info."""
    name = "order_status"

    def handle(self, query: str, order_id: str | None) -> dict:
        oid = order_id or self._extract_order_id(query)
        if not oid:
            return {"reply": "Please share your order ID (e.g. O5001) so I can look it up.",
                    "requires_human": False}
        order = self.tool("order", "get_order", {"order_id": oid})
        if not order.get("ok"):
            return {"reply": f"I couldn't find order **{oid}**. Please double-check the ID.",
                    "requires_human": False}
        ship = self.tool("shipping", "get_shipment", {"order_id": oid})
        o = order["order"]
        s = ship.get("shipment", {})
        reply = (
            f"**Order {oid}** — {o['status'].replace('_',' ')}.\n"
            f"- Placed: {o['placed']}\n"
            f"- Amount: ${o['amount']:.2f}\n"
            f"- Carrier: {s.get('carrier','-')} · tracking `{s.get('tracking','-')}`\n"
            f"- ETA: {s.get('eta','-')}\n"
            f"- Last scan: {s.get('last_scan','-')}"
        )
        return {"reply": reply, "requires_human": False, "order": o, "shipment": s}

    @staticmethod
    def _extract_order_id(text: str) -> str | None:
        m = re.search(r"\bO\d{4,6}\b", text.upper())
        return m.group(0) if m else None
