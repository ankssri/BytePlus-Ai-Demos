"""
BytePlus ModelArk — Seedance 2.0 Portrait Video Demo
Flask backend that proxies all BytePlus API calls.
"""

import os
import base64
import time
from io import BytesIO

import requests
from PIL import Image
from flask import Flask, jsonify, request, render_template
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ── BytePlus configuration ────────────────────────────────────────────
BASE_URL  = "https://ark.ap-southeast.bytepluses.com/api/v3"
API_KEY   = os.getenv("ARK_API_KEY", "")
MODEL_ID  = os.getenv("SEEDANCE_MODEL_ID", "dreamina-seedance-2-0-260128")

ASSETS_GROUP_ENDPOINT  = f"{BASE_URL}/assets/groups"
ASSETS_ENDPOINT        = f"{BASE_URL}/assets"
VIDEO_CREATE_ENDPOINT  = f"{BASE_URL}/contents/generations/tasks"
VIDEO_QUERY_ENDPOINT   = f"{BASE_URL}/contents/generations/tasks"

# ── Helpers ────────────────────────────────────────────────────────

def _headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def _safe_json(resp):
    """Parse a requests.Response as JSON. On failure return a dict with debug info."""
    try:
        return resp.json()
    except Exception:
        return {
            "error": "Non-JSON response from BytePlus API",
            "http_status": resp.status_code,
            "raw_response": resp.text[:500] if resp.text else "(empty body)",
            "url": resp.url,
        }


def _image_to_base64(file_storage) -> str:
    """Convert an uploaded file to a base64 data URI, resizing if needed."""
    image = Image.open(file_storage.stream)

    # Flatten alpha channel
    if image.mode == "RGBA":
        bg = Image.new("RGB", image.size, (255, 255, 255))
        bg.paste(image, mask=image.split()[3])
        image = bg
    elif image.mode != "RGB":
        image = image.convert("RGB")

    # Resize if over 2048 on either axis
    max_dim = 2048
    w, h = image.size
    if w > max_dim or h > max_dim:
        scale = max_dim / max(w, h)
        image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    buf = BytesIO()
    image.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


def _validate_image(file_storage) -> tuple[bool, str, dict]:
    """Return (valid, message, metadata)."""
    try:
        image = Image.open(file_storage.stream)
        file_storage.stream.seek(0)  # reset for later reads
        w, h = image.size
        ratio = w / h
        if image.format not in ("JPEG", "PNG", "WEBP", "BMP", "TIFF", "GIF"):
            return False, f"Unsupported format: {image.format}", {}
        if w < 300 or h < 300:
            return False, f"Image too small ({w}×{h}). Minimum 300×300 px.", {}
        if w > 6000 or h > 6000:
            return False, f"Image too large ({w}×{h}). Maximum 6000×600 px.", {}
        if not (0.4 <= ratio <= 2.5):
            return False, f"Aspect ratio {ratio:.2f} out of range (0.4–2.5).", {}
        meta = {"width": w, "height": h, "format": image.format, "aspect_ratio": round(ratio, 2)}
        return True, "Image is valid", meta
    except Exception as e:
        return False, str(e), {}


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", model_id=MODEL_ID)


@app.route("/api/validate-image", methods=["POST"])
def validate_image_route():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    valid, message, meta = _validate_image(file)
    return jsonify({"valid": valid, "message": message, "meta": meta})


@app.route("/api/create-asset-group", methods=["POST"])
def create_asset_group():
    if not API_KEY:
        return jsonify({"error": "ARK_API_KEY not configured"}), 500

    body = request.json or {}
    name = body.get("name", "Portrait Group")
    description = body.get("description", "Trusted face assets for Seedance 2.0 video generation")

    try:
        resp = requests.post(
            ASSETS_GROUP_ENDPOINT,
            headers=_headers(),
            json={"name": name, "description": description},
            timeout=30,
        )
        print(f"[CreateAssetGroup] status={resp.status_code} url={resp.url}")
        print(f"[CreateAssetGroup] response body: {resp.text[:300]}")
        data = _safe_json(resp)
        if resp.status_code not in (200, 201):
            return jsonify({"error": data, "http_status": resp.status_code}), resp.status_code
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/create-asset", methods=["POST"])
def create_asset():
    if not API_KEY:
        return jsonify({"error": "ARK_API_KEY not configured"}), 500

    group_id = request.form.get("group_id", "")
    asset_name = request.form.get("name", "Portrait Asset")

    if not group_id:
        return jsonify({"error": "group_id is required"}), 400
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    valid, message, _ = _validate_image(file)
    if not valid:
        return jsonify({"error": message}), 400

    try:
        image_b64 = _image_to_base64(file)
    except Exception as e:
        return jsonify({"error": f"Image processing failed: {e}"}), 500

    try:
        resp = requests.post(
            ASSETS_ENDPOINT,
            headers=_headers(),
            json={
                "group_id": group_id,
                "name": asset_name,
                "content_type": "image",
                "url": image_b64,
            },
            timeout=60,
        )
        print(f"[CreateAsset] status={resp.status_code} url={resp.url}")
        print(f"[CreateAsset] response body: {resp.text[:300]}")
        data = _safe_json(resp)
        if resp.status_code not in (200, 201):
            return jsonify({"error": data, "http_status": resp.status_code}), resp.status_code
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/asset-status/<asset_id>", methods=["GET"])
def asset_status(asset_id):
    if not API_KEY:
        return jsonify({"error": "ARK_API_KEY not configured"}), 500
    try:
        resp = requests.get(
            f"{ASSETS_ENDPOINT}/{asset_id}",
            headers=_headers(),
            timeout=15,
        )
        return jsonify(_safe_json(resp)), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/create-video-task", methods=["POST"])
def create_video_task():
    if not API_KEY:
        return jsonify({"error": "ARK_API_KEY not configured"}), 500

    body = request.json or {}
    prompt   = body.get("prompt", "").strip()
    asset_id = body.get("asset_id", "").strip()
    model_id = body.get("model_id", MODEL_ID).strip() or MODEL_ID

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    content = [{"type": "text", "text": prompt}]

    if asset_id:
        # Reference the trusted asset by URI
        content.append({
            "type": "image_url",
            "image_url": {"url": f"asset://{asset_id}"},
            "role": "reference_image",
        })

    payload = {"model": model_id, "content": content}

    try:
        resp = requests.post(
            VIDEO_CREATE_ENDPOINT,
            headers=_headers(),
            json=payload,
            timeout=30,
        )
        print(f"[CreateVideoTask] status={resp.status_code} url={resp.url}")
        print(f"[CreateVideoTask] response body: {resp.text[:300]}")
        data = _safe_json(resp)
        if resp.status_code not in (200, 201):
            return jsonify({"error": data, "http_status": resp.status_code}), resp.status_code
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/video-task/<task_id>", methods=["GET"])
def video_task_status(task_id):
    if not API_KEY:
        return jsonify({"error": "ARK_API_KEY not configured"}), 500
    try:
        resp = requests.get(
            f"{VIDEO_QUERY_ENDPOINT}/{task_id}",
            headers=_headers(),
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


@app.route("/api/config", methods=["GET"])
def api_config():
    return jsonify({
        "api_key_configured": bool(API_KEY),
        "model_id": MODEL_ID,
        "base_url": BASE_URL,
    })


@app.route("/api/debug", methods=["GET"])
def debug_api():
    """Hit the asset-groups endpoint and return raw status + body for diagnostics."""
    if not API_KEY:
        return jsonify({"error": "ARK_API_KEY not configured"}), 500
    try:
        resp = requests.post(
            ASSETS_GROUP_ENDPOINT,
            headers=_headers(),
            json={"name": "_debug_test", "description": "debug"},
            timeout=15,
        )
        return jsonify({
            "http_status": resp.status_code,
            "url_called": resp.url,
            "response_headers": dict(resp.headers),
            "body": resp.text[:1000],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5050))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    print(f"Starting Seedance 2.0 Portrait Demo on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
