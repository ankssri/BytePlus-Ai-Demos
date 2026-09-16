"""FAQ cache: prebuilt answers for common static questions.

Serves without hitting downstream systems or the LLM. The orchestrator
consults this first for FAQ-intent queries.
"""
from __future__ import annotations
import re

FAQ = [
    {
        "id": "faq.return_window",
        "patterns": [r"\breturn (window|policy|period)\b", r"how long.*return", r"can i return"],
        "answer": (
            "Most electronics can be returned within **30 days** of delivery. "
            "Chargers and cables have a **15-day** window. "
            "Items marked *Final Sale / Clearance* are non-returnable."
        ),
    },
    {
        "id": "faq.refund_time",
        "patterns": [r"how long.*refund", r"refund.*take", r"when.*refund"],
        "answer": "Refunds are issued to your original payment method within **5-7 business days** after the warehouse receives your return.",
    },
    {
        "id": "faq.shipping_time",
        "patterns": [r"shipping.*time", r"how long.*ship", r"delivery.*time"],
        "answer": "Standard delivery is **3-5 business days**, Express is **1-2 business days**. Domestic orders ship via SwiftShip, international via GlobeEx.",
    },
    {
        "id": "faq.carriers",
        "patterns": [r"which carrier", r"who.*deliver"],
        "answer": "We use **SwiftShip** for domestic and **GlobeEx** for international deliveries.",
    },
    {
        "id": "faq.contact_human",
        "patterns": [r"speak.*human", r"talk.*agent", r"human agent"],
        "answer": "Sure - I can hand your case to a human agent. Please describe your issue and any relevant order ID and I'll route it.",
    },
]


def lookup(query: str) -> dict | None:
    q = query.lower()
    for item in FAQ:
        for pat in item["patterns"]:
            if re.search(pat, q):
                return item
    return None
