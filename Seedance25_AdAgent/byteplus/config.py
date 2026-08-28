"""Central env accessors + non-secret status. Secrets are read from the
environment only and never logged or returned in full."""

import os

# Public hosts (overridable, not secret)
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")
VIDEO_BASE_URL = os.getenv("VIDEO_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")
TTS_BASE_URL = os.getenv("TTS_BASE_URL", "")  # user-provided when TTS is used

IMAGE_ENDPOINT = f"{IMAGE_BASE_URL}/images/generations"
VIDEO_CREATE_ENDPOINT = f"{VIDEO_BASE_URL}/contents/generations/tasks"
VIDEO_QUERY_ENDPOINT = f"{VIDEO_BASE_URL}/contents/generations/tasks"
LLM_ENDPOINT = f"{LLM_BASE_URL}/chat/completions"

ASSET_HOST = os.getenv("ASSET_HOST", "ark.ap-southeast-1.byteplusapi.com")
ASSET_BASE = f"https://{ASSET_HOST}"
ASSET_VERSION = "2024-01-01"
ASSET_REGION = os.getenv("ASSET_REGION", "ap-southeast-1")
ASSET_SERVICE = os.getenv("ASSET_SERVICE", "ark")


def api_key():          return os.getenv("ARK_API_KEY", "")
def ark_ak():           return os.getenv("ARK_AK", "")
def ark_sk():           return os.getenv("ARK_SK", "")
def seedream_model():   return os.getenv("SEEDREAM_MODEL_ID", "")
def seedance_model():   return os.getenv("SEEDANCE_MODEL_ID", "")
def llm_model():        return os.getenv("SEED_LLM_MODEL_ID", "")
def tts_model():        return os.getenv("TTS_MODEL_ID", "")
def asset_group_id():   return os.getenv("ASSET_GROUP_ID", "")


def status():
    """Non-secret booleans + identifiers for the UI header."""
    return {
        "api_key_configured": bool(api_key()),
        "ak_configured": bool(ark_ak()),
        "sk_configured": bool(ark_sk()),
        "seedream_model_configured": bool(seedream_model()),
        "seedance_model_configured": bool(seedance_model()),
        "llm_model_configured": bool(llm_model()),
        "tts_configured": bool(tts_model() and TTS_BASE_URL),
        "seedream_model_id": seedream_model(),
        "seedance_model_id": seedance_model(),
        "llm_model_id": llm_model(),
        "asset_group_id": asset_group_id(),
    }


def bearer_headers():
    return {"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"}


def safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return {"error": "Non-JSON response", "http_status": resp.status_code,
                "raw_response": (resp.text or "")[:500], "url": resp.url}
