"""
Seedance 2.5 Ad Studio — step-by-step workflow app.

Pipeline:
  1. Load script      : read/paste the two ad markdown files -> structured shots
  2. Generate frames  : Seedream 5.0 pro text-to-image per shot (regenerate / edit)
  3. Upload assets    : register approved keyframe URLs in the Asset Library
  4. Generate video   : Seedance 2.5 first-frame image-to-video per shot,
                        with the shot's dialogue spoken (generate_audio)
  5. Assemble         : collect per-shot clips (+ optional ffmpeg stitch)

All secrets live in .env (never committed, never read by the app author).
See .env.example for the variables you must set.
"""

import glob
import os
import subprocess
import tempfile

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

import byteplus_client as bp
import script_parser

load_dotenv(override=True)

app = Flask(__name__)

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_scripts")


# ── Prompt composition ───────────────────────────────────────────────────────
def compose_video_prompt(shot, speak_dialogue=True, language_label="Hindi"):
    """
    Build the Seedance 2.5 text prompt for a shot: the motion description plus,
    when audio is on, the dialogue in double quotes (BytePlus best practice for
    clean speech generation).
    """
    parts = []
    motion = (shot.get("motion_prompt") or "").strip()
    if motion:
        parts.append(motion)
    else:
        # Fall back to a description built from the shot metadata.
        desc = ", ".join(x for x in [shot.get("camera"), shot.get("action"),
                                     shot.get("setting")] if x)
        if desc:
            parts.append(desc)

    if speak_dialogue:
        line = (shot.get("dialogue_hindi") or "").strip()
        if line:
            eng = (shot.get("dialogue_english") or "").strip()
            hint = f' (English meaning: {eng})' if eng else ""
            parts.append(
                f'The presenter looks at the camera and says in {language_label}: '
                f'"{line}".{hint} Natural lip-sync, warm confident delivery.')
    return " ".join(parts).strip()


# ── Routes: pages & config ───────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", config=bp.config_status())


@app.route("/api/config")
def api_config():
    return jsonify(bp.config_status())


@app.route("/api/samples")
def api_samples():
    """List bundled sample script pairs (script + keyframes)."""
    pairs = {}
    for path in sorted(glob.glob(os.path.join(SAMPLE_DIR, "*.md"))):
        base = os.path.basename(path)
        if base.endswith("_keyframes.md"):
            key = base[:-len("_keyframes.md")]
            pairs.setdefault(key, {})["keyframes"] = base
        elif base.startswith("script_"):
            # e.g. script_A_offer_led.md  -> key 'script_A'
            key = "_".join(base.split("_")[:2])
            pairs.setdefault(key, {})["script"] = base
    out = [{"key": k, **v} for k, v in pairs.items() if "script" in v]
    return jsonify({"samples": out})


@app.route("/api/sample")
def api_sample():
    """Return the raw text of a sample script + keyframes pair by filename."""
    script = request.args.get("script", "")
    keyframes = request.args.get("keyframes", "")

    def _read(name):
        if not name:
            return ""
        safe = os.path.basename(name)
        path = os.path.join(SAMPLE_DIR, safe)
        if not os.path.isfile(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    return jsonify({"script_md": _read(script), "keyframes_md": _read(keyframes)})


REF_SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "static", "sample_refs")
REF_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


@app.route("/api/ref-samples")
def api_ref_samples():
    """List example reference-person images bundled in static/sample_refs/."""
    items = []
    if os.path.isdir(REF_SAMPLE_DIR):
        for name in sorted(os.listdir(REF_SAMPLE_DIR)):
            if name.lower().endswith(REF_EXTS):
                items.append({"name": name,
                              "url": f"/static/sample_refs/{name}"})
    return jsonify({"samples": items})


@app.route("/api/parse-script", methods=["POST"])
def api_parse_script():
    body = request.json or {}
    result = script_parser.parse(body.get("script_md", ""),
                                 body.get("keyframes_md", ""))
    # attach a composed default video prompt per shot for the UI preview
    for shot in result["shots"]:
        shot["video_prompt"] = compose_video_prompt(shot)
    return jsonify(result)


# ── Routes: Step 2 — Seedream keyframe generation / editing ──────────────────
# When a character-reference image is supplied, we DROP the verbal person
# description (it would fight the reference) and instead instruct Seedream to
# copy the exact person from the reference, changing only the scene.
IDENTITY_LOCK_PREFIX = (
    "Keep the EXACT same person shown in the reference image — identical face, "
    "facial features, skin tone, hairstyle, hair length and the same clothing/"
    "outfit. Do not change their identity, age or clothing. Place this exact "
    "same person in the following scene. Scene: "
)


def compose_image_prompt(scene, presenter, has_reference):
    """
    Build the Seedream prompt so identity and scene never conflict:
      - with a reference image  -> reference-pointer + scene only (no verbal
        person description, which would otherwise override the reference)
      - without a reference      -> full presenter description + scene
    """
    scene = (scene or "").strip()
    if has_reference:
        return (IDENTITY_LOCK_PREFIX + scene +
                " Photorealistic, vertical 9:16.").strip()
    presenter = (presenter or "").strip()
    return (f"{presenter} {scene}".strip()
            + (" Photorealistic, vertical 9:16." if scene else "")).strip()


@app.route("/api/generate-keyframe", methods=["POST"])
def api_generate_keyframe():
    body = request.json or {}
    reference = (body.get("reference_image") or "").strip()

    # Preferred path: caller sends `scene` (+ optional `presenter`) and we
    # compose the prompt reference-aware. Legacy path: caller sends a full
    # `prompt` which we use verbatim.
    scene = (body.get("scene") or "").strip()
    presenter = (body.get("presenter") or "").strip()
    if scene:
        prompt = compose_image_prompt(scene, presenter, bool(reference))
    else:
        prompt = (body.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "scene or prompt is required"}), 400

    result, status = bp.seedream_generate(
        prompt=prompt,
        image=reference or None,
        size=body.get("size") or "720x1280",
        guidance_scale=body.get("guidance_scale"),
        watermark=bool(body.get("watermark", False)),
        seed=body.get("seed"),
    )
    result["_prompt"] = prompt  # surfaced for transparency/debugging
    return jsonify(result), status


@app.route("/api/edit-keyframe", methods=["POST"])
def api_edit_keyframe():
    """Edit an existing keyframe: feed the current image back to Seedream with an
    edit instruction (used when a frame is close but not quite right)."""
    body = request.json or {}
    prompt = (body.get("prompt") or "").strip()
    image = (body.get("image") or "").strip()  # url / asset:// / data URI
    if not prompt or not image:
        return jsonify({"error": "prompt and image are both required"}), 400
    result, status = bp.seedream_generate(
        prompt=prompt,
        image=image,
        size=body.get("size") or "720x1280",
        guidance_scale=body.get("guidance_scale"),
        watermark=bool(body.get("watermark", False)),
        seed=body.get("seed"),
    )
    return jsonify(result), status


# ── Routes: Step 3 — Asset Library ───────────────────────────────────────────
@app.route("/api/create-asset", methods=["POST"])
def api_create_asset():
    body = request.json or {}
    group_id = (body.get("group_id") or bp.default_asset_group_id()).strip()
    url = (body.get("url") or "").strip()
    name = (body.get("name") or "keyframe").strip()
    asset_type = (body.get("asset_type") or "Image").strip().capitalize()
    if not group_id:
        return jsonify({"error": "group_id is required (set ASSET_GROUP_ID in .env)"}), 400
    if not url:
        return jsonify({"error": "url is required (publicly accessible)"}), 400
    result, status = bp.create_asset(group_id, url, name, asset_type)
    return jsonify(result), status


@app.route("/api/asset-status/<asset_id>")
def api_asset_status(asset_id):
    result, status = bp.get_asset(asset_id)
    return jsonify(result), status


@app.route("/api/list-assets")
def api_list_assets():
    group_id = (request.args.get("group_id") or bp.default_asset_group_id()).strip()
    if not group_id:
        return jsonify({"error": "group_id is required"}), 400
    result, status = bp.list_assets(group_id)
    return jsonify(result), status


# ── Routes: Step 4 — Seedance 2.5 video ──────────────────────────────────────
@app.route("/api/create-video-task", methods=["POST"])
def api_create_video_task():
    body = request.json or {}
    shot = body.get("shot") or {}
    # A caller may pass an explicit prompt, else compose from the shot.
    prompt = (body.get("prompt") or "").strip() or compose_video_prompt(
        shot, speak_dialogue=bool(body.get("generate_audio", True)))
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    first_frame = (body.get("first_frame") or "").strip()  # asset:// or url
    last_frame = (body.get("last_frame") or "").strip()
    if not first_frame:
        return jsonify({"error": "first_frame (asset:// uri or url) is required"}), 400

    content = bp.build_first_frame_content(prompt, first_frame, last_frame or None)
    result, status = bp.seedance_create(
        content=content,
        resolution=body.get("resolution") or "720p",
        # First-frame i2v on Seedance 2.5 only supports adaptive ratio.
        ratio="adaptive",
        duration=body.get("duration"),
        generate_audio=bool(body.get("generate_audio", True)),
        watermark=bool(body.get("watermark", False)),
        output_format=body.get("output_format") or "mp4",
    )
    return jsonify(result), status


@app.route("/api/video-task/<task_id>")
def api_video_task(task_id):
    result, status = bp.seedance_status(task_id)
    return jsonify(result), status


# ── Routes: Step 5 — assemble (optional local ffmpeg stitch) ─────────────────
@app.route("/api/stitch", methods=["POST"])
def api_stitch():
    """Download the per-shot clips and concatenate them with ffmpeg, if available.
    Returns the local output path. This is a convenience for local runs."""
    body = request.json or {}
    urls = body.get("urls") or []
    if not urls:
        return jsonify({"error": "urls[] required"}), 400
    if not _ffmpeg_available():
        return jsonify({
            "error": "ffmpeg not found on PATH.",
            "hint": "Install ffmpeg, or stitch the clips manually. See README.",
        }), 501

    workdir = tempfile.mkdtemp(prefix="adstudio_")
    list_path = os.path.join(workdir, "concat.txt")
    files = []
    try:
        for i, url in enumerate(urls):
            local = os.path.join(workdir, f"clip_{i:02d}.mp4")
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            with open(local, "wb") as f:
                f.write(r.content)
            files.append(local)
        with open(list_path, "w") as f:
            for local in files:
                f.write(f"file '{local}'\n")
        out_path = os.path.join(workdir, "final_ad.mp4")
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
               "-i", list_path, "-c", "copy", out_path]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            # Retry with re-encode (handles clips with differing params).
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
                   "-c:v", "libx264", "-c:a", "aac", out_path]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            return jsonify({"error": "ffmpeg failed", "stderr": proc.stderr[-800:]}), 500
        return jsonify({"output_path": out_path, "clips": len(files)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _ffmpeg_available():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    print(f"Starting Seedance 2.5 Ad Studio on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
