"""Prompt-injection and PII guards."""
import re

INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above) instructions",
    r"you are now",
    r"system prompt",
    r"disregard.*(policy|rules)",
    r"reveal.*(prompt|instructions|api key|secret)",
    r"</?(system|assistant)>",
]

CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def scan_user_input(text: str) -> dict:
    """Return {clean_text, flags} - flags is a list of triggered guards."""
    flags: list[str] = []
    for p in INJECTION_PATTERNS:
        if re.search(p, text, re.I):
            flags.append(f"prompt_injection:{p}")
    clean = CARD_RE.sub("[REDACTED-CARD]", text)
    if clean != text:
        flags.append("pii_card_number")
    return {"clean_text": clean, "flags": flags}


def redact_for_reply(text: str) -> str:
    return CARD_RE.sub("[REDACTED-CARD]", text)
