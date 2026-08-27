"""
byteplus_client.py — thin API clients for the three BytePlus ModelArk services
used by the Ad Studio workflow.

  1. Seedream 5.0 pro  (image generation + editing)
       Host: ark.ap-southeast.bytepluses.com   Auth: Bearer API Key
       POST /api/v3/images/generations

  2. Asset Library      (CreateAsset / GetAsset / ListAssets / groups)
       Host: ark.ap-southeast-1.byteplusapi.com   Auth: HMAC-SHA256 AK/SK
       POST /?Action=<Action>&Version=2024-01-01

  3. Seedance 2.5       (video generation, image-to-video / omni reference)
       Host: ark.ap-southeast.bytepluses.com   Auth: Bearer API Key
       POST /api/v3/contents/generations/tasks   (+ GET .../{id})

IMPORTANT: All secrets (API key, AK, SK, model ids, endpoints, asset group id)
are read from environment variables only. This module never hard-codes or logs
secret values. Only stdlib `hmac`/`hashlib` are used for signing.
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

import requests

# ── Endpoints (overridable via env; hosts are public, not secret) ────────────
IMAGE_BASE_URL = os.getenv(
    "IMAGE_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")
VIDEO_BASE_URL = os.getenv(
    "VIDEO_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")

IMAGE_ENDPOINT = f"{IMAGE_BASE_URL}/images/generations"
VIDEO_CREATE_ENDPOINT = f"{VIDEO_BASE_URL}/contents/generations/tasks"
VIDEO_QUERY_ENDPOINT = f"{VIDEO_BASE_URL}/contents/generations/tasks"

# ── Asset Library (HMAC AK/SK) ───────────────────────────────────────────────
ASSET_HOST = os.getenv("ASSET_HOST", "ark.ap-southeast-1.byteplusapi.com")
ASSET_BASE = f"https://{ASSET_HOST}"
ASSET_VERSION = "2024-01-01"
ASSET_REGION = os.getenv("ASSET_REGION", "ap-southeast-1")
ASSET_SERVICE = os.getenv("ASSET_SERVICE", "ark")


# ── Env accessors (read fresh so a .env edit + reload is picked up) ───────────
def api_key():
    return os.getenv("ARK_API_KEY", "")


def ark_ak():
    return os.getenv("ARK_AK", "")


def ark_sk():
    return os.getenv("ARK_SK", "")


def seedream_model_id():
    return os.getenv("SEEDREAM_MODEL_ID", "")


def seedance_model_id():
    return os.getenv("SEEDANCE_MODEL_ID", "")


def default_asset_group_id():
    return os.getenv("ASSET_GROUP_ID", "")


def config_status():
    """Non-secret booleans + non-secret identifiers for the UI."""
    return {
        "api_key_configured": bool(api_key()),
        "ak_configured": bool(ark_ak()),
        "sk_configured": bool(ark_sk()),
        "seedream_model_configured": bool(seedream_model_id()),
        "seedance_model_configured": bool(seedance_model_id()),
        "seedream_model_id": seedream_model_id(),
        "seedance_model_id": seedance_model_id(),
        "asset_group_id": default_asset_group_id(),
        "image_endpoint": IMAGE_ENDPOINT,
        "video_endpoint": VIDEO_CREATE_ENDPOINT,
        "asset_host": ASSET_HOST,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────
def _safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return {
            "error": "Non-JSON response from BytePlus API",
            "http_status": resp.status_code,
            "raw_response": (resp.text or "")[:500],
            "url": resp.url,
        }


def _bearer_headers():
    return {
        "Authorization": f"Bearer {api_key()}",
        "Content-Type": "application/json",
    }


# ── 1. Seedream (image gen / edit) ───────────────────────────────────────────
def seedream_generate(prompt, size="720x1280", guidance_scale=None,
                      watermark=False, seed=None, model_id=None,
                      image=None, extra=None):
    """
    Generate (or edit) an image with Seedream.

    - Text-to-image: pass `prompt` only.
    - Image edit / image-to-image: also pass `image` (a public URL, an
      `asset://<id>` uri, or a `data:image/...;base64,...` string). Seedream
      treats the prompt as the edit instruction.

    Returns (result_dict, http_status). On success result_dict has "url".
    """
    if not api_key():
        return {"error": "ARK_API_KEY not configured"}, 500
    mid = (model_id or seedream_model_id()).strip()
    if not mid:
        return {"error": "SEEDREAM_MODEL_ID not configured"}, 500

    payload = {
        "model": mid,
        "prompt": prompt,
        "response_format": "url",
        "watermark": bool(watermark),
    }
    if size:
        payload["size"] = size
    if guidance_scale is not None:
        payload["guidance_scale"] = guidance_scale
    if seed is not None:
        payload["seed"] = seed
    if image:
        # Seedream image-edit input. Some model versions accept a list.
        payload["image"] = image
    if extra:
        payload.update(extra)

    try:
        resp = requests.post(IMAGE_ENDPOINT, headers=_bearer_headers(),
                             json=payload, timeout=120)
        data = _safe_json(resp)
        if resp.status_code not in (200, 201):
            return {"error": data, "http_status": resp.status_code}, resp.status_code
        url = None
        items = data.get("data") or []
        if items and isinstance(items, list):
            url = items[0].get("url") or items[0].get("b64_json")
        if not url:
            return {"error": "No image URL in response", "raw": data}, 502
        return {"url": url, "raw": data}, 200
    except Exception as e:
        return {"error": str(e)}, 500


# ── 2. Asset Library (HMAC-SHA256 AK/SK) ─────────────────────────────────────
def _sign_bytes(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _asset_signed_headers(action, body_str):
    body_hash = hashlib.sha256(body_str.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    dt_str = now.strftime("%Y%m%dT%H%M%SZ")

    canonical_headers = (
        f"content-type:application/json\n"
        f"host:{ASSET_HOST}\n"
        f"x-content-sha256:{body_hash}\n"
        f"x-date:{dt_str}\n"
    )
    signed_headers_str = "content-type;host;x-content-sha256;x-date"
    query = f"Action={action}&Version={ASSET_VERSION}"
    canonical_request = "\n".join([
        "POST", "/", query, canonical_headers, signed_headers_str, body_hash,
    ])
    credential_scope = f"{date_str}/{ASSET_REGION}/{ASSET_SERVICE}/request"
    string_to_sign = "\n".join([
        "HMAC-SHA256", dt_str, credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    k_date = _sign_bytes(ark_sk().encode("utf-8"), date_str)
    k_region = _sign_bytes(k_date, ASSET_REGION)
    k_service = _sign_bytes(k_region, ASSET_SERVICE)
    k_signing = _sign_bytes(k_service, "request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"),
                         hashlib.sha256).hexdigest()
    auth = (
        f"HMAC-SHA256 Credential={ark_ak()}/{credential_scope}, "
        f"SignedHeaders={signed_headers_str}, Signature={signature}"
    )
    return {
        "Content-Type": "application/json",
        "Host": ASSET_HOST,
        "X-Date": dt_str,
        "X-Content-Sha256": body_hash,
        "Authorization": auth,
    }


def asset_call(action, body):
    if not ark_ak() or not ark_sk():
        return {"error": "ARK_AK and ARK_SK are required for asset APIs"}, 500
    body_str = json.dumps(body, separators=(",", ":"))
    url = f"{ASSET_BASE}/?Action={action}&Version={ASSET_VERSION}"
    headers = _asset_signed_headers(action, body_str)
    try:
        resp = requests.post(url, headers=headers, data=body_str, timeout=30)
        print(f"[asset:{action}] status={resp.status_code}")
        return _safe_json(resp), resp.status_code
    except Exception as e:
        return {"error": str(e)}, 500


def create_asset(group_id, url, name, asset_type="Image"):
    body = {
        "GroupId": group_id,
        "URL": url,
        "AssetType": asset_type,
        "Name": name,
        "ProjectName": "default",
    }
    data, status = asset_call("CreateAsset", body)
    if status not in (200, 201) or "error" in data:
        return {"error": data, "http_status": status}, max(status, 400)
    asset_id = (data.get("Result") or {}).get("Id")
    return {"id": asset_id, "raw": data}, 200


def get_asset(asset_id):
    data, status = asset_call("GetAsset", {"Id": asset_id, "ProjectName": "default"})
    result = data.get("Result") or {}
    return {
        "id": asset_id,
        "status": result.get("Status", ""),
        "url": result.get("URL", ""),
        "raw": data,
    }, status


def list_assets(group_id, page_size=50):
    body = {
        "Filter": {"GroupIds": [group_id], "GroupType": "AIGC"},
        "PageNumber": 1, "PageSize": page_size,
        "SortBy": "CreateTime", "SortOrder": "Desc", "ProjectName": "default",
    }
    data, status = asset_call("ListAssets", body)
    if status not in (200, 201) or "error" in data:
        return {"error": data, "http_status": status}, max(status, 400)
    items = (data.get("Result") or {}).get("Items") or []
    assets = [{"id": a.get("Id"), "name": a.get("Name"), "url": a.get("URL"),
               "asset_type": a.get("AssetType"), "status": a.get("Status")}
              for a in items]
    return {"assets": assets}, 200


# ── 3. Seedance 2.5 (video) ──────────────────────────────────────────────────
def seedance_create(content, model_id=None, resolution="720p", ratio="adaptive",
                    duration=None, generate_audio=True, watermark=False,
                    output_format="mp4", seed=None, extra=None):
    """
    Create a Seedance 2.5 video task. `content` is the ready-built content[]
    list (text + image/video/audio references). Returns (result, http_status);
    on success result has "id" (task id).
    """
    if not api_key():
        return {"error": "ARK_API_KEY not configured"}, 500
    mid = (model_id or seedance_model_id()).strip()
    if not mid:
        return {"error": "SEEDANCE_MODEL_ID not configured"}, 500

    payload = {
        "model": mid,
        "content": content,
        "resolution": resolution,
        "ratio": ratio,
        "generate_audio": bool(generate_audio),
        "watermark": bool(watermark),
        "output_format": output_format,
    }
    if duration is not None:
        payload["duration"] = duration
    if seed is not None:
        payload["seed"] = seed
    if extra:
        payload.update(extra)

    try:
        resp = requests.post(VIDEO_CREATE_ENDPOINT, headers=_bearer_headers(),
                             json=payload, timeout=60)
        data = _safe_json(resp)
        if resp.status_code not in (200, 201):
            return {"error": data, "http_status": resp.status_code, "_request": payload}, resp.status_code
        return {"id": data.get("id"), "raw": data, "_request": payload}, 200
    except Exception as e:
        return {"error": str(e)}, 500


def seedance_status(task_id):
    if not api_key():
        return {"error": "ARK_API_KEY not configured"}, 500
    try:
        resp = requests.get(f"{VIDEO_QUERY_ENDPOINT}/{task_id}",
                            headers=_bearer_headers(), timeout=30)
        data = _safe_json(resp)
        content = data.get("content") or {}
        video_url = content.get("video_url") or data.get("video_url")
        last_frame = content.get("last_frame_url")
        return {
            "id": task_id,
            "status": data.get("status", ""),
            "video_url": video_url,
            "last_frame_url": last_frame,
            "error": data.get("error"),
            "raw": data,
        }, resp.status_code
    except Exception as e:
        return {"error": str(e)}, 500


def build_first_frame_content(text, first_frame_ref, last_frame_ref=None):
    """
    Build the content[] for a Seedance 2.5 first-frame (or first+last) image-to-video
    task. Refs may be `asset://<id>`, a public https URL, or a data: URI.
    """
    content = [{"type": "text", "text": text}]
    content.append({
        "type": "image_url",
        "role": "first_frame",
        "image_url": {"url": first_frame_ref},
    })
    if last_frame_ref:
        content.append({
            "type": "image_url",
            "role": "last_frame",
            "image_url": {"url": last_frame_ref},
        })
    return content
