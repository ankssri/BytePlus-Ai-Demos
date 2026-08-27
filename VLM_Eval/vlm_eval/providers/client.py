"""OpenAI-compatible chat client used for both Seed (Ark) and Gemini.

Both BytePlus ModelArk and Google Gemini expose an OpenAI-style
`POST {base_url}/chat/completions` surface, so one client serves both. The
class also encapsulates the *fair-shot* handling that the customer benchmark
was missing for Seed:

  * an optional JSON `response_format` so the model is asked for machine JSON,
  * retries on transport errors and unparseable JSON,
  * per-request timeout and latency measurement,
  * robust extraction of JSON even when the model wraps it in prose/fences.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

from ..config import ProviderConfig, max_retries, request_timeout
from ..utils import extract_json, image_to_data_url


@dataclass
class ChatResult:
    provider: str
    model: str
    text: str                       # assistant message content
    latency_s: float                # wall-clock for the successful call
    ok: bool                        # transport + HTTP succeeded
    json_obj: Optional[Any] = None  # parsed JSON when a structured task asked for it
    json_valid: bool = False        # True only if structured parse succeeded
    attempts: int = 1
    error: Optional[str] = None
    usage: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


class ChatClient:
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self.timeout = request_timeout()
        self.retries = max_retries()

    # -- message construction --------------------------------------------------
    @staticmethod
    def build_messages(prompt: str, image_paths: list[str] | None = None,
                       system: str | None = None) -> list[dict]:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        content: list[dict] = []
        for p in (image_paths or []):
            content.append({
                "type": "image_url",
                "image_url": {"url": image_to_data_url(p)},
            })
        content.append({"type": "text", "text": prompt})
        messages.append({"role": "user", "content": content})
        return messages

    # -- core call -------------------------------------------------------------
    def chat(
        self,
        prompt: str,
        image_paths: list[str] | None = None,
        *,
        system: str | None = None,
        expect_json: bool = False,
        json_object: bool = False,
        max_tokens: int = 2048,
        temperature: float | None = None,
        extra_body: dict | None = None,
    ) -> ChatResult:
        """Run a single chat completion.

        When ``expect_json`` is True the reply is parsed and retried up to
        ``MAX_RETRIES`` times if it does not contain valid JSON.
        """
        messages = self.build_messages(prompt, image_paths, system)

        body: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if json_object:
            body["response_format"] = {"type": "json_object"}
        # Provider defaults (e.g. Seed thinking toggle) then per-call overrides.
        body.update(self.cfg.extra_body or {})
        if extra_body:
            body.update(extra_body)

        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.cfg.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Optional[str] = None
        attempts = 0
        # One base attempt plus retries; retries only add value when we need
        # valid JSON or hit a transient transport error.
        total = 1 + (self.retries if expect_json else self.retries)
        for attempt in range(1, total + 1):
            attempts = attempt
            start = time.time()
            try:
                resp = requests.post(url, json=body, headers=headers, timeout=self.timeout)
                latency = time.time() - start
                if resp.status_code >= 400:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:400]}"
                    # 4xx other than 429 won't fix themselves; stop early.
                    if resp.status_code != 429 and resp.status_code < 500:
                        return ChatResult(self.cfg.name, self.cfg.model, "", latency,
                                          ok=False, attempts=attempts, error=last_error)
                    continue
                data = resp.json()
                text = _first_message_text(data)
                usage = data.get("usage") or {}
                if expect_json:
                    obj = extract_json(text)
                    if obj is None:
                        last_error = "invalid/empty JSON"
                        # Retry with a stronger nudge for the next attempt.
                        _nudge_json(body)
                        continue
                    return ChatResult(self.cfg.name, self.cfg.model, text, latency,
                                      ok=True, json_obj=obj, json_valid=True,
                                      attempts=attempts, usage=usage, raw=data)
                return ChatResult(self.cfg.name, self.cfg.model, text, latency,
                                  ok=True, attempts=attempts, usage=usage, raw=data)
            except requests.Timeout:
                last_error = f"timeout after {self.timeout}s"
            except Exception as e:  # network / decode
                last_error = f"{type(e).__name__}: {e}"

        return ChatResult(self.cfg.name, self.cfg.model, "", 0.0,
                          ok=False, attempts=attempts, error=last_error)


def _first_message_text(data: dict) -> str:
    try:
        msg = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return ""
    content = msg.get("content")
    if isinstance(content, str):
        return content
    # Some gateways return content as a list of parts.
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def _nudge_json(body: dict) -> None:
    """Append a corrective instruction to the last user message for a retry."""
    try:
        user = body["messages"][-1]
        parts = user["content"]
        if isinstance(parts, list):
            parts.append({
                "type": "text",
                "text": "Return ONLY a valid JSON object. No prose, no markdown fences.",
            })
    except Exception:
        pass
