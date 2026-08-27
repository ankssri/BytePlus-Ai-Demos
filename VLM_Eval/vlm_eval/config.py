"""Configuration loading for VLM_Eval.

Reads endpoints, model IDs and API keys from the environment (optionally via a
`.env` file). Secrets live only in `.env` (git-ignored) and are never logged.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Load .env if present. We keep this dependency-optional so the package still
# imports when python-dotenv is missing (keys can be exported in the shell).
try:  # pragma: no cover - trivial
    from dotenv import load_dotenv

    _ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_ENV_PATH)
except Exception:  # pragma: no cover
    pass


@dataclass
class ProviderConfig:
    """Everything needed to call one OpenAI-compatible chat endpoint."""

    name: str          # short id used in reports, e.g. "seed" / "gemini"
    label: str         # human label, e.g. "dola-seed-2-1-turbo-260628"
    api_key: str
    base_url: str
    model: str
    # Provider-specific extras merged into every request body.
    extra_body: dict

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def seed_config() -> ProviderConfig:
    thinking = _env("SEED_THINKING", "disabled").lower()
    extra: dict = {}
    if thinking in ("disabled", "enabled", "auto"):
        # Ark Chat API accepts a `thinking` object to toggle deep reasoning.
        extra["thinking"] = {"type": thinking}
    model = _env("SEED_MODEL", "dola-seed-2-1-turbo-260628")
    return ProviderConfig(
        name="seed",
        label=model,
        api_key=_env("SEED_API_KEY"),
        base_url=_env("SEED_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3"),
        model=model,
        extra_body=extra,
    )


def gemini_config() -> ProviderConfig:
    model = _env("GEMINI_MODEL", "gemini-3.1-pro-preview")
    return ProviderConfig(
        name="gemini",
        label=model,
        api_key=_env("GEMINI_API_KEY"),
        base_url=_env("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"),
        model=model,
        extra_body={},
    )


def request_timeout() -> float:
    try:
        return float(_env("REQUEST_TIMEOUT", "120"))
    except ValueError:
        return 120.0


def max_retries() -> int:
    try:
        return int(_env("MAX_RETRIES", "2"))
    except ValueError:
        return 2


def judge_provider_name() -> str:
    return _env("JUDGE_PROVIDER", "gemini").lower()


def all_providers() -> dict[str, ProviderConfig]:
    return {"seed": seed_config(), "gemini": gemini_config()}
