"""Shared helpers: image encoding and robust JSON extraction."""
from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Any, Optional


def image_to_data_url(path: str | Path) -> str:
    """Encode a local image as a `data:` URL usable by both providers."""
    path = Path(path)
    mime, _ = mimetypes.guess_type(str(path))
    if mime is None:
        # Fall back based on suffix; default to png.
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(path.suffix.lower(), "image/png")
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{data}"


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> Optional[Any]:
    """Best-effort parse of a JSON object/array out of a model reply.

    Handles: clean JSON, ```json fenced blocks, and JSON embedded in prose.
    Returns the parsed object or None if nothing parseable is found.
    """
    if not text:
        return None
    text = text.strip()

    # 1) Direct parse.
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2) Fenced code block.
    m = _FENCE_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass

    # 3) First balanced {...} or [...] span.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except Exception:
                        break
    return None


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
