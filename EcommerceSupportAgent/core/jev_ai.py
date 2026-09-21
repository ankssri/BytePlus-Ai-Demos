"""Jev (TypeSafe System One) adapter — typed judgments for intent + FAQ routing.

Uses the `jev` SDK (https://pypi.org/project/jev/) when it's installed and
TYPESAFE_API_KEY is set. Otherwise every function raises NotAvailable so
the caller falls back to its existing rule-based path.

Design note: Jev returns typed values with calibrated probabilities. The
`jev` decorator SDK collapses probabilities to argmax, which is enough
for a demo — for confidence-gated routing in production we'd use
`typesafe-sdk` directly. We still get "unclear" branches because we
include a `none / unclear` option in every Literal, and the model picks
it when nothing fits.
"""
from __future__ import annotations
import os
from typing import Literal
from dataclasses import dataclass


class NotAvailable(RuntimeError):
    pass


def _ensure() -> None:
    if not os.environ.get("TYPESAFE_API_KEY"):
        raise NotAvailable("TYPESAFE_API_KEY not set")
    try:
        import jev  # noqa: F401
        from pydantic import BaseModel  # noqa: F401
    except ImportError as e:
        raise NotAvailable(f"jev SDK not installed: {e}")


def available() -> bool:
    try:
        _ensure()
        return True
    except NotAvailable:
        return False


# ---------------------------------------------------------------- Intent
IntentLabel = Literal[
    "faq", "order_status", "return_refund", "human_handoff", "unclear",
]


@dataclass
class IntentDecision:
    intent: IntentLabel
    needs_order_context: bool


def classify_intent(text: str) -> IntentDecision:
    """Ask Jev what the customer wants. Raises NotAvailable if SDK/key missing."""
    _ensure()
    import jev
    from pydantic import BaseModel, Field

    class _Intent(BaseModel):
        intent: IntentLabel = Field(
            description=(
                "The customer's intent. 'faq' for policy or generic questions with "
                "no order id required. 'order_status' to look up shipping/tracking. "
                "'return_refund' to return an item or request a refund. "
                "'human_handoff' if the customer explicitly asks for a human. "
                "'unclear' if none of the above clearly applies."
            )
        )
        needs_order_context: bool = Field(
            description="True if answering requires an order id or account lookup."
        )

    @jev.fn
    def _classify(message: str) -> _Intent:
        """A message from an e-commerce customer to a support agent:

        {{ message }}
        """
        return _classify.state()

    r = _classify(text)
    return IntentDecision(intent=r.intent, needs_order_context=r.needs_order_context)


# ---------------------------------------------------------------- FAQ router
FaqId = Literal[
    "faq.return_window", "faq.refund_time", "faq.shipping_time",
    "faq.carriers", "faq.contact_human", "none",
]


@dataclass
class FaqDecision:
    faq_id: FaqId


def match_faq(text: str) -> FaqDecision:
    """Semantic FAQ router. 'none' means the question doesn't match a canned answer."""
    _ensure()
    import jev
    from pydantic import BaseModel, Field

    class _Match(BaseModel):
        faq_id: FaqId = Field(
            description=(
                "Which canned FAQ answers the customer's question. "
                "'faq.return_window' - what the return window / return policy is. "
                "'faq.refund_time' - how long refunds take to appear. "
                "'faq.shipping_time' - standard/express delivery timing. "
                "'faq.carriers' - which shipping carriers are used. "
                "'faq.contact_human' - customer wants to speak to a person. "
                "'none' - question is specific to their order/account or off-topic."
            )
        )

    @jev.fn
    def _route(message: str) -> _Match:
        """An e-commerce customer's question:

        {{ message }}
        """
        return _route.state()

    r = _route(text)
    return FaqDecision(faq_id=r.faq_id)
