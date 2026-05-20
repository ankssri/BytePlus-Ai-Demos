"""
BytePlus ModelArk — Seedance 2.0 Studio

A workflow-oriented video generation demo:
  • Browse asset groups & assets (image / video / audio) with previews
  • Compose a generation by combining a text prompt with up to one
    image + one video + one audio reference at the same time
  • Submit to Seedance 2.0 and watch the resulting video inline

Two auth schemes (same as Seedance2_Portrait_Demo, reused verbatim):
  Asset APIs  → ark.ap-southeast-1.byteplusapi.com  (HMAC-SHA256 AK/SK)
  Video APIs  → ark.ap-southeast.bytepluses.com     (Bearer API key)
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

VALID_ASSET_TYPES = {"Image", "Video", "Audio"}

REFERENCE_FIELDS = {
    "Image": ("image_url", "reference_image"),
    "Video": ("video_url", "reference_video"),
    "Audio": ("audio_url", "reference_audio"),
}


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
    if not ARK_AK or not ARK_SK:
        return {"error": "ARK_AK and ARK_SK are required for asset APIs"}, 500

    body_str = json.dumps(body, separators=(",", ":"))
    url      = f"{ASSET_BASE}/?Action={action}&Version={ASSET_VERSION}"
    headers  = _asset_signed_headers(action, body_str)

    try:
        resp = requests.post(url, headers=headers, data=body_str, timeout=30)
        return _safe_json(resp), resp.status_code
    except Exception as e:
        return {"error": str(e)}, 500


def _parse_prompt_flags(prompt: str) -> tuple:
    """Extract --ratio, --duration, --resolution flags from prompt text."""
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


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", model_id=MODEL_ID)


@app.route("/api/config", methods=["GET"])
def api_config():
    return jsonify({
        "api_key_configured": bool(API_KEY),
        "ak_configured": bool(ARK_AK),
        "sk_configured": bool(ARK_SK),
        "model_id": MODEL_ID,
    })


# ── Asset groups ──────────────────────────────────────────────────────────────

@app.route("/api/groups", methods=["GET"])
def list_groups():
    """List ALL asset groups by paginating server-side until exhausted."""
    page_size = int(request.args.get("page_size", 100))
    max_pages = int(request.args.get("max_pages", 50))

    groups = []
    total = 0
    for page_number in range(1, max_pages + 1):
        body = {
            "Filter": {"GroupType": "AIGC"},
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
        total  = result.get("TotalCount", total)
        groups.extend(
            {"id": g.get("Id"), "name": g.get("Name"), "description": g.get("Description", "")}
            for g in items
        )
        if len(items) < page_size or len(groups) >= total > 0:
            break

    return jsonify({"groups": groups, "total": total or len(groups)})


@app.route("/api/groups/<group_id>/assets", methods=["GET"])
def list_group_assets(group_id):
    """List assets in a group, optionally filtered by type (Image|Video|Audio)."""
    asset_type = request.args.get("type", "").strip().capitalize()
    page_size  = int(request.args.get("page_size", 100))
    max_pages  = int(request.args.get("max_pages", 10))

    if not group_id:
        return jsonify({"error": "group_id is required"}), 400

    filt = {"GroupIds": [group_id], "GroupType": "AIGC"}
    if asset_type in VALID_ASSET_TYPES:
        filt["AssetType"] = asset_type

    assets = []
    total  = 0
    for page_number in range(1, max_pages + 1):
        body = {
            "Filter":      filt,
            "PageNumber":  page_number,
            "PageSize":    page_size,
            "SortBy":      "CreateTime",
            "SortOrder":   "Desc",
            "ProjectName": "default",
        }
        data, status_code = _call_asset_api("ListAssets", body)
        if status_code not in (200, 201) or "error" in data:
            return jsonify({"error": data, "http_status": status_code}), max(status_code, 400)

        result = data.get("Result") or {}
        items  = result.get("Items") or []
        total  = result.get("TotalCount", total)
        assets.extend(
            {
                "id":         a.get("Id"),
                "name":       a.get("Name"),
                "url":        a.get("URL"),
                "asset_type": a.get("AssetType"),
                "status":     a.get("Status"),
                "group_id":   a.get("GroupId"),
                "created_at": a.get("CreateTime"),
            }
            for a in items
        )
        if len(items) < page_size or len(assets) >= total > 0:
            break

    return jsonify({"assets": assets, "total": total or len(assets)})


@app.route("/api/asset/<asset_id>", methods=["GET"])
def get_asset(asset_id):
    body = {"Id": asset_id, "ProjectName": "default"}
    data, status_code = _call_asset_api("GetAsset", body)
    if status_code not in (200, 201) or "error" in data:
        return jsonify({"error": data, "http_status": status_code}), max(status_code, 400)
    result = data.get("Result") or {}
    return jsonify({
        "id":         result.get("Id"),
        "name":       result.get("Name"),
        "url":        result.get("URL"),
        "asset_type": result.get("AssetType"),
        "status":     result.get("Status"),
        "group_id":   result.get("GroupId"),
        "created_at": result.get("CreateTime"),
    })


# ── Video generation ──────────────────────────────────────────────────────────

@app.route("/api/generate", methods=["POST"])
def generate_video():
    """
    Submit a Seedance 2.0 video generation task.

    Body:
      {
        "prompt":     str (required),
        "model_id":   str (optional, defaults to SEEDANCE_MODEL_ID),
        "references": [
          {"type": "Image" | "Video" | "Audio",
           "asset_id": "...", OR "url": "https://..."}
        ],
        "options": {"ratio": "16:9", "duration": 5, "resolution": "1080p"}
      }
    """
    if not API_KEY:
        return jsonify({"error": "ARK_API_KEY not configured"}), 500

    body_in    = request.json or {}
    prompt     = (body_in.get("prompt") or "").strip()
    model_id   = (body_in.get("model_id") or MODEL_ID).strip()
    references = body_in.get("references") or []
    options    = body_in.get("options") or {}

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    clean_prompt, prompt_extras = _parse_prompt_flags(prompt)

    content = [{"type": "text", "text": clean_prompt}]
    for ref in references:
        ref_type = (ref.get("type") or "").capitalize()
        if ref_type not in VALID_ASSET_TYPES:
            continue
        asset_id = (ref.get("asset_id") or "").strip()
        url      = (ref.get("url") or "").strip()
        if not asset_id and not url:
            continue
        type_key, role = REFERENCE_FIELDS[ref_type]
        ref_url = f"asset://{asset_id}" if asset_id else url
        content.append({
            "type":   type_key,
            "role":   role,
            type_key: {"url": ref_url},
        })

    # options object takes precedence over prompt flags
    extras = {**prompt_extras}
    for k in ("ratio", "duration", "resolution"):
        v = options.get(k)
        if v not in (None, ""):
            extras[k] = v

    payload = {
        "model":     model_id,
        "content":   content,
        "watermark": False,
        **extras,
    }

    try:
        resp = requests.post(
            VIDEO_CREATE_ENDPOINT,
            headers=_video_headers(),
            json=payload,
            timeout=30,
        )
        data = _safe_json(resp)
        if resp.status_code not in (200, 201):
            return jsonify({"error": data, "http_status": resp.status_code}), resp.status_code
        data["_byteplus_request"] = payload
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/task/<task_id>", methods=["GET"])
def video_task_status(task_id):
    if not API_KEY:
        return jsonify({"error": "ARK_API_KEY not configured"}), 500
    try:
        resp = requests.get(
            f"{VIDEO_QUERY_ENDPOINT}/{task_id}",
            headers=_video_headers(),
            timeout=15,
        )
        data = _safe_json(resp)

        # Best-effort extract of video_url across response shapes
        video_url = (
            (data.get("content") or {}).get("video_url")
            or data.get("video_url")
            or ((data.get("result") or {}).get("video_url"))
            or ((data.get("data") or {}).get("video_url"))
        )
        status = (
            data.get("status")
            or (data.get("result") or {}).get("status")
            or (data.get("data") or {}).get("status")
        )
        return jsonify({
            "task_id":   task_id,
            "status":    status,
            "video_url": video_url,
            "raw":       data,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5051"))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
