"""
Seedance 2.5 Ad Agent — idea → brand ad video.

Stages: Brief → Script (LLM or paste) → Brand Kit (omni refs) → Storyboard
preview → ONE long-form Seedance 2.5 generation → Edit/extend → Post overlays →
export. See DESIGN.md.

All secrets are read from .env only (never logged or returned in full).
"""

import glob
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from byteplus import assets, config as C, llm, seedance, seedream, tts

load_dotenv(override=True)

app = Flask(__name__)
HERE = os.path.dirname(__file__)
BRIEF_DIR = os.path.join(HERE, "sample_briefs")
REF_DIR = os.path.join(HERE, "static", "sample_refs")


# ── pages / config ───────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", config=C.status())


@app.route("/api/config")
def api_config():
    return jsonify(C.status())


@app.route("/api/sample-briefs")
def api_sample_briefs():
    items = []
    for p in sorted(glob.glob(os.path.join(BRIEF_DIR, "*.md"))):
        items.append({"name": os.path.basename(p)})
    return jsonify({"briefs": items})


@app.route("/api/sample-brief")
def api_sample_brief():
    name = os.path.basename(request.args.get("name", ""))
    path = os.path.join(BRIEF_DIR, name)
    if not (name and os.path.isfile(path)):
        return jsonify({"error": "not found"}), 404
    with open(path, encoding="utf-8") as f:
        return jsonify({"text": f.read()})


@app.route("/api/ref-samples")
def api_ref_samples():
    items = []
    if os.path.isdir(REF_DIR):
        for n in sorted(os.listdir(REF_DIR)):
            if n.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                items.append({"name": n, "url": f"/static/sample_refs/{n}"})
    return jsonify({"samples": items})


# ── Prompt optimizer (sd25-pe equivalent) ───────────────────────────────────
@app.route("/api/optimize-prompt", methods=["POST"])
def api_optimize_prompt():
    b = request.json or {}
    prompt = (b.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    result, status = llm.optimize_seedance_prompt(
        prompt, duration=int(b.get("duration") or 20), aspect=b.get("aspect") or "9:16")
    return jsonify(result), status


# ── Stage 1: script agent ────────────────────────────────────────────────────
@app.route("/api/generate-plan", methods=["POST"])
def api_generate_plan():
    b = request.json or {}
    brief = (b.get("brief") or "").strip()
    if not brief:
        return jsonify({"error": "brief is required"}), 400
    result, status = llm.generate_ad_plan(
        brief=brief,
        duration=int(b.get("duration") or 20),
        aspect=b.get("aspect") or "9:16",
        language=b.get("language") or "Hindi + English",
        model_text=bool(b.get("model_text", False)),
    )
    return jsonify(result), status


# ── Stage 2/3: Seedream (brand kit assets + storyboard frames) ───────────────
@app.route("/api/seedream", methods=["POST"])
def api_seedream():
    b = request.json or {}
    prompt = (b.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    result, status = seedream.generate(
        prompt=prompt, size=b.get("size") or "2K",
        image=(b.get("image") or None), seed=b.get("seed"),
        optimize_prompt=b.get("optimize_prompt", True))
    return jsonify(result), status


@app.route("/api/prepare-face", methods=["POST"])
def api_prepare_face():
    """Turn an uploaded real-person photo into a model-generated (trusted) hosted
    image URL that Seedance will accept as a reference."""
    b = request.json or {}
    image = (b.get("image") or "").strip()
    if not image:
        return jsonify({"error": "image (base64/url) is required"}), 400
    result, status = seedream.trusted_url_for_face(image, size=b.get("size") or "720x1280")
    return jsonify(result), status


# ── Asset library ────────────────────────────────────────────────────────────
@app.route("/api/create-asset", methods=["POST"])
def api_create_asset():
    b = request.json or {}
    group_id = (b.get("group_id") or C.asset_group_id()).strip()
    url = (b.get("url") or "").strip()
    if not group_id:
        return jsonify({"error": "group_id required (set ASSET_GROUP_ID)"}), 400
    if not url:
        return jsonify({"error": "url required (public)"}), 400
    result, status = assets.create(group_id, url, (b.get("name") or "asset").strip(),
                                   (b.get("asset_type") or "Image").strip().capitalize())
    return jsonify(result), status


@app.route("/api/asset-status/<asset_id>")
def api_asset_status(asset_id):
    result, status = assets.get(asset_id)
    return jsonify(result), status


def build_asset_bindings(images, audios, labels=None):
    """Enumerate references by upload order so the model's @Image N / @Audio N
    numbering is unambiguous (Seedance best practice: bind each asset in text)."""
    lines = []
    for i, _ in enumerate(images, start=1):
        lbl = (labels[i - 1] if labels and i - 1 < len(labels) and labels[i - 1]
               else ("the main presenter/subject — keep this exact identity" if i == 1
                     else "a reference image"))
        lines.append(f"@Image {i} = {lbl}")
    for j, _ in enumerate(audios, start=1):
        lines.append(f"@Audio {j} = the voiceover; lip-sync the speaker to it")
    if not lines:
        return ""
    return ("Asset bindings (by upload order): " + "; ".join(lines)
            + ". Use exactly these bindings in the action below.\n\n")


# ── Stage 4: Seedance long-form generation ───────────────────────────────────
@app.route("/api/generate-video", methods=["POST"])
def api_generate_video():
    b = request.json or {}
    brief = (b.get("director_brief") or "").strip()
    if not brief:
        return jsonify({"error": "director_brief is required"}), 400
    duration = b.get("duration")
    if duration is not None:
        duration = max(4, min(30, int(duration)))
    images = [u for u in (b.get("reference_images") or []) if u]
    audios = [u for u in (b.get("reference_audios") or []) if u]
    # Prepend explicit asset bindings so @Image N / @Audio N map to upload order.
    text = build_asset_bindings(images, audios, b.get("reference_labels")) + brief
    content = seedance.build_omni_content(
        text=text, reference_images=images, reference_audios=audios)
    result, status = seedance.create(
        content=content,
        resolution=b.get("resolution") or "720p",
        ratio=b.get("aspect") or "9:16",
        duration=duration,
        generate_audio=bool(b.get("generate_audio", True)),
        omni_reference_task_type="reference",
    )
    return jsonify(result), status


@app.route("/api/video-task/<task_id>")
def api_video_task(task_id):
    result, status = seedance.status(task_id)
    return jsonify(result), status


# ── Stage 5: edit / extend ───────────────────────────────────────────────────
@app.route("/api/edit-video", methods=["POST"])
def api_edit_video():
    b = request.json or {}
    if not (b.get("video_url") and b.get("instruction")):
        return jsonify({"error": "video_url and instruction required"}), 400
    result, status = seedance.edit(b["video_url"].strip(), b["instruction"].strip(),
                                   generate_audio=bool(b.get("generate_audio", True)))
    return jsonify(result), status


@app.route("/api/extend-video", methods=["POST"])
def api_extend_video():
    b = request.json or {}
    if not (b.get("video_url") and b.get("instruction")):
        return jsonify({"error": "video_url and instruction required"}), 400
    result, status = seedance.extend(b["video_url"].strip(), b["instruction"].strip(),
                                     generate_audio=bool(b.get("generate_audio", True)))
    return jsonify(result), status


# ── VO mode B: TTS ───────────────────────────────────────────────────────────
@app.route("/api/tts", methods=["POST"])
def api_tts():
    b = request.json or {}
    text = (b.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    result, status = tts.synthesize(text, voice=b.get("voice"),
                                    language=b.get("language") or "hi")
    return jsonify(result), status


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8090))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    print(f"Starting Seedance 2.5 Ad Agent on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
