"""LLM adapter for BytePlus ModelArk, with a deterministic offline fallback.

Set env vars to use the real model:
    ARK_API_KEY=<key>
    ARK_MODEL=<endpoint id, e.g. ep-2025...>
    ARK_BASE_URL=https://ark.ap-southeast.bytepluses.com/api/v3   (default)

If ARK_API_KEY is missing OR the SDK is not installed, a lightweight
rule-based fallback classifier / drafter is used so the demo runs
anywhere without keys.
"""
from __future__ import annotations
import json, os, re

_ARK = None
_MODEL = os.environ.get("ARK_MODEL", "")
_BASE = os.environ.get("ARK_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")


def _client():
    global _ARK
    if _ARK is not None:
        return _ARK
    key = os.environ.get("ARK_API_KEY")
    if not key:
        return None
    try:
        from byteplussdkarkruntime import Ark
        _ARK = Ark(api_key=key, base_url=_BASE)
        return _ARK
    except Exception:
        return None


def chat(system: str, user: str, *, max_tokens: int = 400, temperature: float = 0.2) -> str:
    cli = _client()
    if cli is None or not _MODEL:
        return _offline_reply(system, user)
    try:
        resp = cli.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=temperature, max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"[llm-error: {e}] " + _offline_reply(system, user)


# ---- offline fallback --------------------------------------------------

INTENT_RULES = [
    ("faq",           r"\b(policy|policies|window|how long|refund time|shipping time|carrier)\b"),
    ("order_status",  r"\b(where.*order|order status|track|tracking|shipped|arriving|delivery)\b"),
    ("return_refund", r"\b(return|refund|money back|send back)\b"),
    ("human_handoff", r"\b(human|agent|representative|manager)\b"),
]


def classify_intent(text: str) -> str:
    t = text.lower()
    for intent, pat in INTENT_RULES:
        if re.search(pat, t):
            return intent
    return "faq"


def _offline_reply(system: str, user: str) -> str:
    if "return a JSON" in system or "respond in JSON" in system.lower():
        # try to satisfy JSON-shape callers deterministically
        return json.dumps({"intent": classify_intent(user), "notes": "offline-fallback"})
    return (
        "I can help with returns, refunds, order status, and store policy questions. "
        "Please share your order ID (e.g. O5001) and what you need."
    )
