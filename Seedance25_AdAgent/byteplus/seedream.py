"""Seedream 5.0 pro — image generation & editing (brand-kit assets, storyboard
frames, identity-preserving pass for uploaded faces)."""

import requests

from . import config as C


def compose_image_prompt(subject, environment="", composition="", style="",
                         lighting="", quality="high quality, ultra-fine, 2K"):
    """
    Build a Seedream 5.0 prompt in the recommended 6-part order:
    Picture Quality + Subject & Features + Environment + Composition & Shot +
    Style & Atmosphere + Lighting & Color. Content in natural language; aesthetics
    as short phrases.
    """
    parts = [quality, subject, environment, composition, style, lighting]
    return ". ".join(p.strip() for p in parts if p and p.strip()).strip()


def generate(prompt, size="2K", watermark=False, seed=None, model_id=None,
             image=None, optimize_prompt=None, sequential=False, extra=None):
    """
    Text-to-image, or image edit / identity pass when `image` is given
    (public URL, asset:// uri, or data:image/...;base64,...).
    - size: "1K"/"2K"/"4K" or "WxH" (2K recommended for storyboard frames)
    - optimize_prompt: let Seedream's VLM rewrite colloquial prompts (default on)
    - sequential: set sequential_image_generation=auto to make a consistent SET
    Returns (result, http_status); on success result has "url".
    """
    if not C.api_key():
        return {"error": "ARK_API_KEY not configured"}, 500
    mid = (model_id or C.seedream_model()).strip()
    if not mid:
        return {"error": "SEEDREAM_MODEL_ID not configured"}, 500

    payload = {"model": mid, "prompt": prompt, "response_format": "url",
               "watermark": bool(watermark)}
    if size:
        payload["size"] = size
    if seed is not None:
        payload["seed"] = seed
    if image:
        payload["image"] = image
    if optimize_prompt is not None:
        payload["optimize_prompt"] = bool(optimize_prompt)
    if sequential:
        payload["sequential_image_generation"] = "auto"
    if extra:
        payload.update(extra)

    try:
        resp = requests.post(C.IMAGE_ENDPOINT, headers=C.bearer_headers(),
                             json=payload, timeout=180)
        data = C.safe_json(resp)
        if resp.status_code not in (200, 201):
            return {"error": data, "http_status": resp.status_code}, resp.status_code
        items = data.get("data") or []
        url = items[0].get("url") if items else None
        if not url:
            return {"error": "No image URL in response", "raw": data}, 502
        return {"url": url, "raw": data}, 200
    except Exception as e:
        return {"error": str(e)}, 500


def trusted_url_for_face(image, size="720x1280"):
    """
    Turn an uploaded real-person photo into a MODEL-GENERATED, publicly hosted
    image (Seedream identity pass), so it can be registered as a trusted Asset
    for Seedance (which rejects raw real-face uploads). Returns (result, status).
    """
    return generate(
        prompt=("Recreate this exact person as a clean, well-lit, front-facing "
                "photorealistic portrait — keep identical face, features, skin "
                "tone, hair and clothing. Neutral studio background."),
        image=image, size=size)
