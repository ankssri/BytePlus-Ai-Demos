"""
BytePlus ModelArk — Seedance 2.0 Real-Human Portrait Video Demo

Two separate auth schemes:
  Asset APIs  → Host: ark.ap-southeast-1.byteplusapi.com
                Auth: HMAC-SHA256 AK/SK signature
                Pattern: POST /?Action=<Action>&Version=2024-01-01

  Video APIs  → Host: ark.ap-southeast.bytepluses.com
                Auth: Bearer API Key
                Pattern: REST /api/v3/contents/generations/tasks

Real-human groups use GroupType: "LivenessFace".
Authorization letter must be signed in the BytePlus console before
the first CreateAssetGroup call.
"""

import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)

# ── Video generation (Bearer token) ─────────────────────────────────────────
VIDEO_BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
API_KEY        = os.getenv("ARK_API_KEY", "")
MODEL_ID       = os.getenv("SEEDANCE_MODEL_ID", "dreamina-seedance-2-0-260128")

VIDEO_CREATE_ENDPOINT = f"{VIDEO_BASE_URL}/contents/generations/tasks"
VIDEO_QUERY_ENDPOINT  = f"{VIDEO_BASE_URL}/contents/generations/tasks"

# ── Asset library (HMAC-SHA256 AK/SK) ───────────────────────────────────────
ASSET_HOST    = "ark.ap-southeast-1.byteplusapi.com"
ASSET_BASE    = f"https://{ASSET_HOST}"
ASSET_VERSION = "2024-01-01"
ASSET_REGION  = "ap-southeast-1"
ASSET_SERVICE = "ark"

ARK_AK = os.getenv("ARK_AK", "")
ARK_SK = os.getenv("ARK_SK", "")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_json(resp) -> dict:
    try:
        return resp.json()
    except Exception:
        return {
            "error": "Non-JSON response from BytePlus API",
            "http_status": resp.status_code,
            "raw_response": resp.text[:500] if resp.text else "(empty body)",
            "url": resp.url,
        }


def _video_headers() -> dict:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def _sign_bytes(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _asset_signed_headers(action: str, body_str: str) -> dict:
    """Build HMAC-SHA256 signed headers for BytePlus Asset API calls."""
    body_hash = hashlib.sha256(body_str.encode("utf-8")).hexdigest()
    now       = datetime.now(timezone.utc)
    date_str  = now.strftime("%Y%m%d")
    dt_str    = now.strftime("%Y%m%dT%H%M%SZ")

    canonical_headers = (
        f"content-type:application/json\n"
        f"host:{ASSET_HOST}\n"
        f"x-content-sha256:{body_hash}\n"
        f"x-date:{dt_str}\n"
    )
    signed_headers_str = "content-type;host;x-content-sha256;x-date"
    query = f"Action={action}&Version={ASSET_VERSION}"

    canonical_request = "\n".join([
        "POST", "/", query,
        canonical_headers, signed_headers_str, body_hash,
    ])

    credential_scope = f"{date_str}/{ASSET_REGION}/{ASSET_SERVICE}/request"
    string_to_sign = "\n".join([
        "HMAC-SHA256",
        dt_str,
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])

    k_date    = _sign_bytes(ARK_SK.encode("utf-8"), date_str)
    k_region  = _sign_bytes(k_date, ASSET_REGION)
    k_service = _sign_bytes(k_region, ASSET_SERVICE)
    k_signing = _sign_bytes(k_service, "request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    auth = (
        f"HMAC-SHA256 Credential={ARK_AK}/{credential_scope}, "
        f"SignedHeaders={signed_headers_str}, "
        f"Signature={signature}"
    )

    return {
        "Content-Type":     "application/json",
        "Host":             ASSET_HOST,
        "X-Date":           dt_str,
        "X-Content-Sha256": body_hash,
        "Authorization":    auth,
    }


def _call_asset_api(action: str, body: dict) -> tuple:
    """Call a BytePlus Asset API with HMAC-SHA256 auth."""
    if not ARK_AK or not ARK_SK:
        return {"error": "ARK_AK and ARK_SK are required for asset APIs"}, 500

    body_str = json.dumps(body, separators=(",", ":"))
    url      = f"{ASSET_BASE}/?Action={action}&Version={ASSET_VERSION}"
    headers  = _asset_signed_headers(action, body_str)

    try:
        resp = requests.post(url, headers=headers, data=body_str, timeout=30)
        print(f"[{action}] status={resp.status_code} url={resp.url}")
        print(f"[{action}] response={resp.text[:400]}")
        return _safe_json(resp), resp.status_code
    except Exception as e:
        return {"error": str(e)}, 500


def _parse_prompt_flags(prompt: str) -> tuple:
    """Extract --ratio, --duration, --resolution flags; return (clean_prompt, extras_dict)."""
    extras = {}
    for pattern, key, cast in [
        (r'--ratio\s+(\S+)',      'ratio',      str),
        (r'--duration\s+(\d+)',   'duration',   int),
        (r'--resolution\s+(\S+)', 'resolution', str),
    ]:
        m = re.search(pattern, prompt)
        if m:
            extras[key] = cast(m.group(1))
            prompt = (prompt[:m.start()] + prompt[m.end():]).strip()
    return prompt.strip(), extras


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", model_id=MODEL_ID)


@app.route("/api/config", methods=["GET"])
def api_config():
    return jsonify({
        "api_key_configured": bool(API_KEY),
        "ak_configured":      bool(ARK_AK),
        "sk_configured":      bool(ARK_SK),
        "model_id":           MODEL_ID,
        "video_base_url":     VIDEO_BASE_URL,
        "asset_host":         ASSET_HOST,
    })


# ── Asset Groups ──────────────────────────────────────────────────────────────

@app.route("/api/list-asset-groups", methods=["GET"])
def list_asset_groups():
    """
    POST /?Action=ListAssetGroups&Version=2024-01-01
    Filter: { GroupType: "LivenessFace" } — real-human portrait groups only.
    """
    page_number = int(request.args.get("page", 1))
    page_size   = int(request.args.get("page_size", 50))

    body = {
        "Filter": {
            "GroupType": "LivenessFace",
        },
        "PageNumber":  page_number,
        "PageSize":    page_size,
        "SortBy":      "CreateTime",
        "SortOrder":   "Desc",
        "ProjectName": "default",
    }
    data, status_code = _call_asset_api("ListAssetGroups", body)

    if status_code not in (200, 201) or "error" in data:
        return jsonify({"error": data, "http_status": status_code}), max(status_code, 400)

    result = data.get("Result") or {}
    items  = result.get("Items") or []
    groups = [
        {"id": g.get("Id"), "name": g.get("Name"), "description": g.get("Description", "")}
        for g in items
    ]
    return jsonify({"groups": groups, "total": result.get("TotalCount", len(groups))})


@app.route("/api/create-asset-group", methods=["POST"])
def create_asset_group():
    """
    POST /?Action=CreateAssetGroup&Version=2024-01-01
    GroupType must be "LivenessFace" for real-human portrait groups.
    Authorization letter must be signed in the console before the first call.
    """
    body_in = request.json or {}
    body = {
        "Name":        body_in.get("name", "Real-Human Portrait Group"),
        "Description": body_in.get("description", ""),
        "GroupType":   "LivenessFace",
        "ProjectName": "default",
    }
    data, status_code = _call_asset_api("CreateAssetGroup", body)

    if status_code not in (200, 201) or "error" in data:
        return jsonify({"error": data, "http_status": status_code}), max(status_code, 400)

    group_id = (data.get("Result") or {}).get("Id")
    return jsonify({"id": group_id, "raw": data})


# ── Assets ────────────────────────────────────────────────────────────────────

@app.route("/api/create-asset", methods=["POST"])
def create_asset():
    """
    POST /?Action=CreateAsset&Version=2024-01-01
    Supports AssetType: Image | Video | Audio.
    URL must be a publicly accessible HTTPS URL — no base64.
    Optional: Moderation: { Strategy: "Skip" } — requires Secure Mode OFF in console first.
    """
    body_in    = request.json or {}
    group_id   = body_in.get("group_id", "").strip()
    asset_name = body_in.get("name", "Portrait Asset").strip()
    asset_url  = body_in.get("url", "").strip()
    asset_type = body_in.get("asset_type", "Image").strip()  # Image | Video | Audio
    skip_moderation = body_in.get("skip_moderation", False)

    if not group_id:
        return jsonify({"error": "group_id is required"}), 400
    if not asset_url:
        return jsonify({"error": "url is required — must be a publicly accessible HTTPS URL"}), 400
    if asset_type not in ("Image", "Video", "Audio"):
        return jsonify({"error": "asset_type must be Image, Video, or Audio"}), 400

    body = {
        "GroupId":     group_id,
        "URL":         asset_url,
        "AssetType":   asset_type,
        "Name":        asset_name,
        "ProjectName": "default",
    }
    if skip_moderation:
        body["Moderation"] = {"Strategy": "Skip"}

    data, status_code = _call_asset_api("CreateAsset", body)

    if status_code not in (200, 201) or "error" in data:
        return jsonify({"error": data, "http_status": status_code}), max(status_code, 400)

    asset_id = (data.get("Result") or {}).get("Id")
    return jsonify({"id": asset_id, "raw": data})


@app.route("/api/asset-status/<asset_id>", methods=["GET"])
def asset_status(asset_id):
    """
    POST /?Action=GetAsset&Version=2024-01-01
    Status values: Active | Processing | Failed
    Note: URL in response is only valid for 12 hours.
    """
    body = {"Id": asset_id, "ProjectName": "default"}
    data, status_code = _call_asset_api("GetAsset", body)
    result = (data.get("Result") or {})
    return jsonify({
        "id":         asset_id,
        "status":     result.get("Status", ""),
        "asset_type": result.get("AssetType", ""),
        "url":        result.get("URL", ""),
        "raw":        data,
    }), status_code


@app.route("/api/list-assets", methods=["GET"])
def list_assets():
    """
    POST /?Action=ListAssets&Version=2024-01-01
    Filter by GroupId and optionally Statuses and Name.
    """
    group_id = request.args.get("group_id", "").strip()
    if not group_id:
        return jsonify({"error": "group_id query parameter is required"}), 400

    body = {
        "Filter": {
            "GroupIds": [group_id],
            "GroupType": "LivenessFace",
        },
        "PageNumber": 1,
        "PageSize":   50,
        "SortBy":     "CreateTime",
        "SortOrder":  "Desc",
        "ProjectName": "default",
    }
    data, status_code = _call_asset_api("ListAssets", body)

    if status_code not in (200, 201) or "error" in data:
        return jsonify({"error": data, "http_status": status_code}), max(status_code, 400)

    result = data.get("Result") or {}
    items  = result.get("Items") or []
    assets = [
        {
            "id":         a.get("Id"),
            "name":       a.get("Name", ""),
            "asset_type": a.get("AssetType", ""),
            "status":     a.get("Status", ""),
            "group_id":   a.get("GroupId", ""),
        }
        for a in items
    ]
    return jsonify({"assets": assets, "total": result.get("TotalCount", len(assets))})


# ── Video generation ──────────────────────────────────────────────────────────

@app.route("/api/create-video-task", methods=["POST"])
def create_video_task():
    """
    POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks
    Auth: Bearer API Key

    Multi-asset support: pass assets as a list [{asset_id, asset_type}].
    In the prompt reference them positionally: "Image 1", "Audio 1" etc.
    generate_audio: true enables AI-generated audio in the video.
    """
    if not API_KEY:
        return jsonify({"error": "ARK_API_KEY not configured"}), 500

    body_in       = request.json or {}
    prompt        = body_in.get("prompt", "").strip()
    assets        = body_in.get("assets", [])   # [{asset_id, asset_type}]
    model_id      = (body_in.get("model_id", "") or MODEL_ID).strip()
    generate_audio = body_in.get("generate_audio", False)

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    clean_prompt, extras = _parse_prompt_flags(prompt)

    content = [{"type": "text", "text": clean_prompt}]

    for asset in assets:
        asset_id   = (asset.get("asset_id") or "").strip()
        asset_type = (asset.get("asset_type") or "Image").strip()
        if not asset_id:
            continue

        if asset_type == "Audio":
            content.append({
                "type": "audio_url",
                "role": "reference_audio",
                "audio_url": {"url": f"asset://{asset_id}"},
            })
        else:
            content.append({
                "type": "image_url",
                "role": "reference_image",
                "image_url": {"url": f"asset://{asset_id}"},
            })

    payload = {
        "model":   model_id,
        "content": content,
        "watermark": False,
        **extras,
    }
    if generate_audio:
        payload["generate_audio"] = True

    try:
        resp = requests.post(
            VIDEO_CREATE_ENDPOINT,
            headers=_video_headers(),
            json=payload,
            timeout=30,
        )
        print(f"[CreateVideoTask] status={resp.status_code}")
        print(f"[CreateVideoTask] response={resp.text[:400]}")
        data = _safe_json(resp)
        if resp.status_code not in (200, 201):
            return jsonify({"error": data, "http_status": resp.status_code}), resp.status_code
        data["_byteplus_request"] = payload
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/video-task/<task_id>", methods=["GET"])
def video_task_status(task_id):
    """
    GET /api/v3/contents/generations/tasks/{id}
    Auth: Bearer API Key
    """
    if not API_KEY:
        return jsonify({"error": "ARK_API_KEY not configured"}), 500
    try:
        resp = requests.get(
            f"{VIDEO_QUERY_ENDPOINT}/{task_id}",
            headers=_video_headers(),
            timeout=15,
        )
        data = _safe_json(resp)

        video_url = (
            (data.get("content") or {}).get("video_url")
            or data.get("video_url")
            or ((data.get("result") or {}).get("video_url"))
            or ((data.get("data") or {}).get("video_url"))
            or ((data.get("output") or {}).get("video_url"))
            or ((data.get("video") or {}).get("url"))
        )
        if video_url:
            data["_video_url"] = video_url

        return jsonify(data), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port  = int(os.getenv("PORT", 5051))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    print(f"Starting Real-Human Portrait Demo on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
