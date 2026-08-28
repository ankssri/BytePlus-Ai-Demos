"""Seedance 2.5 — long-form (≤30s) video with omni references + edit/extend.

Key API constraint (BytePlus docs): first_frame/last_frame image-to-video is
MUTUALLY EXCLUSIVE with omni reference-to-video. To combine an approved opening
frame WITH brand-kit references, we use OMNI-REFERENCE mode (all images as
`reference_image`) and tell the model, in the prompt, to open on the first
reference image. That's the officially recommended way to get a
"first/last frame + omni references" effect.
"""

import requests

from . import config as C

IMG, VID, AUD = "image_url", "video_url", "audio_url"


def build_omni_content(text, reference_images=None, reference_videos=None,
                       reference_audios=None):
    """
    Build content[] for an omni reference-to-video (or edit/extend) request.
    Each ref may be a public URL, a data: URI, or `asset://<id>`.
    reference_images: list of urls  (presenter, product, logo, style, approved frames)
    reference_videos: list of urls  (the prior generated ad, for edit/extend)
    reference_audios: list of urls  (VO track for mode B)
    """
    content = [{"type": "text", "text": text}]
    for u in (reference_images or []):
        content.append({"type": IMG, "role": "reference_image", IMG: {"url": u}})
    for u in (reference_videos or []):
        content.append({"type": VID, "role": "reference_video", VID: {"url": u}})
    for u in (reference_audios or []):
        content.append({"type": AUD, "role": "reference_audio", AUD: {"url": u}})
    return content


def create(content, resolution="720p", ratio="9:16", duration=None,
           generate_audio=True, watermark=False, output_format="mp4",
           omni_reference_task_type="auto", seed=None, model_id=None, extra=None):
    """Create a Seedance 2.5 task. Returns (result, http_status); result has 'id'."""
    if not C.api_key():
        return {"error": "ARK_API_KEY not configured"}, 500
    mid = (model_id or C.seedance_model()).strip()
    if not mid:
        return {"error": "SEEDANCE_MODEL_ID not configured"}, 500

    payload = {"model": mid, "content": content, "resolution": resolution,
               "ratio": ratio, "generate_audio": bool(generate_audio),
               "watermark": bool(watermark), "output_format": output_format}
    if omni_reference_task_type:
        payload["omni_reference_task_type"] = omni_reference_task_type
    if duration is not None:
        payload["duration"] = duration
    if seed is not None:
        payload["seed"] = seed
    if extra:
        payload.update(extra)

    try:
        resp = requests.post(C.VIDEO_CREATE_ENDPOINT, headers=C.bearer_headers(),
                             json=payload, timeout=60)
        data = C.safe_json(resp)
        if resp.status_code not in (200, 201):
            return {"error": data, "http_status": resp.status_code, "_request": payload}, resp.status_code
        return {"id": data.get("id"), "raw": data, "_request": payload}, 200
    except Exception as e:
        return {"error": str(e)}, 500


def status(task_id):
    if not C.api_key():
        return {"error": "ARK_API_KEY not configured"}, 500
    try:
        resp = requests.get(f"{C.VIDEO_QUERY_ENDPOINT}/{task_id}",
                            headers=C.bearer_headers(), timeout=30)
        data = C.safe_json(resp)
        content = data.get("content") or {}
        return {"id": task_id, "status": data.get("status", ""),
                "video_url": content.get("video_url") or data.get("video_url"),
                "last_frame_url": content.get("last_frame_url"),
                "error": data.get("error"), "raw": data}, resp.status_code
    except Exception as e:
        return {"error": str(e)}, 500


def edit(video_url, instruction, generate_audio=True, output_format="mov", extra=None):
    """Timestamp/segment edit of an existing ad. `ratio`=adaptive, `duration`=-1
    are required for edit tasks per the 2.5 spec."""
    content = build_omni_content(instruction, reference_videos=[video_url])
    return create(content, ratio="adaptive", duration=-1, generate_audio=generate_audio,
                  output_format=output_format, omni_reference_task_type="edit", extra=extra)


def extend(video_url, instruction, generate_audio=True, extra=None):
    """Extend an existing ad forward/backward. `ratio`=adaptive for extend tasks."""
    content = build_omni_content(instruction, reference_videos=[video_url])
    return create(content, ratio="adaptive", duration=None, generate_audio=generate_audio,
                  omni_reference_task_type="extend", extra=extra)
