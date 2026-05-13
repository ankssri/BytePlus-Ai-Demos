"""
BytePlus ModelArk — Seedance 2.0 Portrait Video Demo

Two separate auth schemes (confirmed from official BytePlus docs):
  Asset APIs  → Host: ark.ap-southeast-1.byteplusapi.com
                Auth: HMAC-SHA256 AK/SK signature
                Pattern: POST /?Action=<Action>&Version=2024-01-01

  Video APIs  → Host: ark.ap-southeast.bytepluses.com
                Auth: Bearer API Key
                Pattern: REST /api/v3/contents/generations/tasks
"""

import base64
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from io import BytesIO

import requests
from PIL import Image
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
        "Content-Type":    "application/json",
        "Host":            ASSET_HOST,
        "X-Date":          dt_str,
        "X-Content-Sha256": body_hash,
        "Authorization":   auth,
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


def _validate_image_file(file_storage):
    try:
        image = Image.open(file_storage.stream)
        file_storage.stream.seek(0)
        w, h = image.size
        ratio = w / h
        if image.format not in ("JPEG", "PNG", "WEBP", "BMP", "TIFF", "GIF"):
            return False, f"Unsupported format: {image.format}", {}
        if w < 300 or h < 300:
            return False, f"Image too small ({w}×{h}). Minimum 300×300 px.", {}
        if w > 6000 or h > 6000:
            return False, f"Image too large ({w}×{h}). Maximum 6000×6000 px.", {}
        if not (0.4 <= ratio <= 2.5):
            return False, f"Aspect ratio {ratio:.2f} out of range (0.4–2.5).", {}
        meta = {"width": w, "height": h, "format": image.format, "aspect_ratio": round(ratio, 2)}
        return True, "Image is valid", meta
    except Exception as e:
        return False, str(e), {}


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


def _image_to_base64(file_storage) -> str:
    image = Image.open(file_storage.stream)
    if image.mode == "RGBA":
        bg = Image.new("RGB", image.size, (255, 255, 255))
        bg.paste(image, mask=image.split()[3])
        image = bg
    elif image.mode != "RGB":
        image = image.convert("RGB")
    max_dim = 2048
    w, h = image.size
    if w > max_dim or h > max_dim:
        scale = max_dim / max(w, h)
        image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=90)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"


# ── Routes ────────────────────────────────────────────────────────────────────

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
        "video_base_url": VIDEO_BASE_URL,
        "asset_host": ASSET_HOST,
    })


@app.route("/api/validate-image", methods=["POST"])
def validate_image_route():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400
    file = request.files["image"]
    valid, message, meta = _validate_image_file(file)
    return jsonify({"valid": valid, "message": message, "meta": meta})


# ── Asset Group ───────────────────────────────────────────────────────────────

@app.route("/api/list-asset-groups", methods=["GET"])
def list_asset_groups():
    """
    POST https://ark.ap-southeast-1.byteplusapi.com/?Action=ListAssetGroups&Version=2024-01-01
    Body: { Filter: { GroupType (required), Name?, GroupIds? }, PageNumber, PageSize, SortBy, SortOrder, ProjectName }
    Response: { Result: { TotalCount, Items: [{Id, Name, Description, GroupType, CreateTime, ...}], PageNumber, PageSize } }
    """
    page_number = int(request.args.get("page", 1))
    page_size   = int(request.args.get("page_size", 50))

    body = {
        "Filter": {
            "GroupType": "AIGC",
        },
        "PageNumber":   page_number,
        "PageSize":     page_size,
        "SortBy":       "CreateTime",
        "SortOrder":    "Desc",
        "ProjectName":  "default",
    }
    data, status_code = _call_asset_api("ListAssetGroups", body)

    if status_code not in (200, 201) or "error" in data:
        return jsonify({"error": data, "http_status": status_code}), max(status_code, 400)

    result = data.get("Result") or {}
    items  = result.get("Items") or []
    groups = [{"id": g.get("Id"), "name": g.get("Name"), "description": g.get("Description", "")}
              for g in items]
    return jsonify({"groups": groups, "total": result.get("TotalCount", len(groups))})


@app.route("/api/create-asset-group", methods=["POST"])
def create_asset_group():
    """
    POST https://ark.ap-southeast-1.byteplusapi.com/?Action=CreateAssetGroup&Version=2024-01-01
    Body: { Name, Description, GroupType, ProjectName }
    Response wraps result in: { ResponseMetadata: {...}, Result: { Id: "group-..." } }
    """
    body_in = request.json or {}
    body = {
        "Name":        body_in.get("name", "Portrait Group"),
        "Description": body_in.get("description", ""),
        "GroupType":   "AIGC",
        "ProjectName": "default",
    }
    data, status_code = _call_asset_api("CreateAssetGroup", body)

    if status_code not in (200, 201) or "error" in data:
        return jsonify({"error": data, "http_status": status_code}), max(status_code, 400)

    group_id = (data.get("Result") or {}).get("Id")
    return jsonify({"id": group_id, "raw": data})


# ── Asset ─────────────────────────────────────────────────────────────────────

VALID_ASSET_TYPES = {"Image", "Video", "Audio"}


@app.route("/api/create-asset", methods=["POST"])
def create_asset():
    """
    POST https://ark.ap-southeast-1.byteplusapi.com/?Action=CreateAsset&Version=2024-01-01
    Body: { GroupId, URL (public URL only — base64 not supported), AssetType, Name, ProjectName }
    AssetType: "Image" | "Video" | "Audio"
    Response: { ResponseMetadata: {...}, Result: { Id: "asset-..." } }
    """
    body_in    = request.json or {}
    group_id   = body_in.get("group_id", "").strip()
    asset_name = body_in.get("name", "Portrait Asset").strip()
    asset_url  = body_in.get("url", "").strip()
    asset_type = (body_in.get("asset_type", "Image") or "Image").strip().capitalize()

    if not group_id:
        return jsonify({"error": "group_id is required"}), 400
    if not asset_url:
        return jsonify({"error": "url is required — must be a publicly accessible URL"}), 400
    if asset_type not in VALID_ASSET_TYPES:
        return jsonify({"error": f"asset_type must be one of {sorted(VALID_ASSET_TYPES)}"}), 400

    body = {
        "GroupId":     group_id,
        "URL":         asset_url,
        "AssetType":   asset_type,
        "Name":        asset_name,
        "ProjectName": "default",
    }
    data, status_code = _call_asset_api("CreateAsset", body)

    if status_code not in (200, 201) or "error" in data:
        return jsonify({"error": data, "http_status": status_code}), max(status_code, 400)

    asset_id = (data.get("Result") or {}).get("Id")
    return jsonify({"id": asset_id, "asset_type": asset_type, "raw": data})


@app.route("/api/asset-status/<asset_id>", methods=["GET"])
def asset_status(asset_id):
    """
    POST https://ark.ap-southeast-1.byteplusapi.com/?Action=GetAsset&Version=2024-01-01
    Body: { Id, ProjectName }
    Response Status values: Active | Processing | Failed
    """
    body = {"Id": asset_id, "ProjectName": "default"}
    data, status_code = _call_asset_api("GetAsset", body)
    result = (data.get("Result") or {})
    status = result.get("Status", "")
    return jsonify({"id": asset_id, "status": status, "raw": data}), status_code


# ── Video generation ──────────────────────────────────────────────────────────

@app.route("/api/create-video-task", methods=["POST"])
def create_video_task():
    """
    POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks
    Auth: Bearer API Key
    Supports: asset URI (asset://<id>) or direct public image URL in content array.
    In the prompt, reference images positionally: "Image 1", "Image 2" etc.
    """
    if not API_KEY:
        return jsonify({"error": "ARK_API_KEY not configured"}), 500

    body_in  = request.json or {}
    prompt   = body_in.get("prompt", "").strip()
    asset_id = body_in.get("asset_id", "").strip()
    img_url  = body_in.get("image_url", "").strip()
    model_id = (body_in.get("model_id", "") or MODEL_ID).strip()

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    # Extract --ratio / --duration / --resolution inline flags into top-level fields
    clean_prompt, extras = _parse_prompt_flags(prompt)

    content = [{"type": "text", "text": clean_prompt}]

    if asset_id:
        content.append({
            "type": "image_url",
            "role": "reference_image",
            "image_url": {"url": f"asset://{asset_id}"},
        })
    elif img_url:
        content.append({
            "type": "image_url",
            "role": "reference_image",
            "image_url": {"url": img_url},
        })
    elif img_url:
        content.append({
            "type": "image_url",
            "image_url": {"url": img_url},
            "role": "reference_image",
        })

    payload = {
        "model":     model_id,
        "content":   content,
        "watermark": False,
        **extras,           # ratio, duration, resolution (if present)
    }

    try:
        resp = requests.post(
            VIDEO_CREATE_ENDPOINT,
            headers=_video_headers(),
            json=payload,
            timeout=30,
        )
        print(f"[CreateVideoTask] status={resp.status_code} url={resp.url}")
        print(f"[CreateVideoTask] response={resp.text[:400]}")
        data = _safe_json(resp)
        if resp.status_code not in (200, 201):
            return jsonify({"error": data, "http_status": resp.status_code}), resp.status_code
        # Include the actual BytePlus payload so the frontend inspector can display it
        data["_byteplus_request"] = payload
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/video-task/<task_id>", methods=["GET"])
def video_task_status(task_id):
    """
    GET https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks/{id}
    Auth: Bearer API Key
    Response: { id, model, status, content: { video_url }, created_at, updated_at }
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

        # Normalise video URL from multiple possible response shapes
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


@app.route("/api/debug-asset", methods=["GET"])
def debug_asset():
    """Raw connectivity test for the asset API endpoint."""
    body = {"Name": "_debug", "GroupType": "AIGC", "ProjectName": "default"}
    body_str = json.dumps(body, separators=(",", ":"))
    url = f"{ASSET_BASE}/?Action=CreateAssetGroup&Version={ASSET_VERSION}"
    try:
        headers = _asset_signed_headers("CreateAssetGroup", body_str)
        resp = requests.post(url, headers=headers, data=body_str, timeout=15)
        return jsonify({
            "http_status": resp.status_code,
            "url_called": url,
            "body": resp.text[:1000],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port  = int(os.getenv("PORT", 5050))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    print(f"Starting Seedance 2.0 Portrait Demo on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
