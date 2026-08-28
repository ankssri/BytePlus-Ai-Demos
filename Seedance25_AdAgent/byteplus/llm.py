"""Seed LLM (Chat API) script agent — turns a brief into a structured Ad Plan
using json_schema structured output."""

import json

import requests

from . import config as C
from schemas import AD_PLAN_SCHEMA

SYSTEM = (
    "You are an expert short-form advertising creative director and scriptwriter. "
    "You design vertical (9:16) social video ads that are ONE continuous piece of "
    "video (not separate clips) suitable for the Seedance 2.5 video model, which "
    "handles cuts and pacing itself. You write bilingual Hindi + English ad copy: "
    "spoken voiceover in natural Hindi (Devanagari) with English product terms. "
    "You keep the whole ad within the requested duration and lead with a strong hook."
)


def _text_rule(model_text):
    if model_text:
        return ("On-screen text policy (HYBRID): the video model may render ONLY very "
                "short English/number badges (e.g. '₹2.45 Lakh', '7-Yr Warranty'). "
                "Put those in each scene's on_screen_text. All Hindi text, phone numbers, "
                "addresses and the logo go in overlay_text (composited in post) — never in "
                "on_screen_text. In director_brief, mention the short English badges as "
                "on-screen text.")
    return ("On-screen text policy (POST-ONLY): the video model renders NO text. Leave "
            "on_screen_text empty for every scene. All text (badges, Hindi, contact, logo) "
            "goes in overlay_text for post compositing, and director_brief must not ask the "
            "model to render any text.")


def generate_ad_plan(brief, duration=20, aspect="9:16", language="Hindi + English",
                     model_text=False, model_id=None):
    """Call the Seed LLM with strict json_schema and return (ad_plan_dict, http_status)."""
    if not C.api_key():
        return {"error": "ARK_API_KEY not configured"}, 500
    mid = (model_id or C.llm_model()).strip()
    if not mid:
        return {"error": "SEED_LLM_MODEL_ID not configured (paste a brief/plan instead, or set it in .env)"}, 500

    user = (
        f"Create an ad plan.\n\nBRIEF:\n{brief}\n\n"
        f"Constraints: language = {language}; total duration = {duration} seconds "
        f"(all scene times must fit within 0..{duration}); aspect = {aspect}.\n"
        f"{_text_rule(model_text)}\n"
        "Write 3-6 scenes on a single timeline, a strong opening hook, a clear CTA at the end, "
        "and a director_brief that describes the entire ad as one coherent video with each "
        "spoken line in double quotes."
    )

    payload = {
        "model": mid,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": user}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "ad_plan", "strict": True,
                                            "schema": AD_PLAN_SCHEMA}},
        "thinking": {"type": "disabled"},
    }
    try:
        resp = requests.post(C.LLM_ENDPOINT, headers=C.bearer_headers(),
                             json=payload, timeout=120)
        data = C.safe_json(resp)
        if resp.status_code not in (200, 201):
            return {"error": data, "http_status": resp.status_code}, resp.status_code
        content = (((data.get("choices") or [{}])[0]).get("message") or {}).get("content", "")
        try:
            plan = json.loads(content)
        except Exception:
            return {"error": "Model did not return valid JSON", "raw": content[:800]}, 502
        return {"plan": plan, "raw": data}, 200
    except Exception as e:
        return {"error": str(e)}, 500
