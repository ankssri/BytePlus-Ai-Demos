"""
Seedance 2.5 Image-to-Video — Streamlit demo.

Generates videos from a reference image using the Higgsfield API
(model: bytedance/seedance-2.5/image-to-video) via the official
`higgsfield-client` Python SDK.

Credentials are loaded at runtime from `.env.local` (git-ignored) as
`HF_KEY=KEY_ID:KEY_SECRET`. The SDK reads `HF_KEY` from the environment
itself, so the value is never handled, printed, or logged by this app.
"""

from __future__ import annotations

import io
import os
import mimetypes

import streamlit as st
from dotenv import load_dotenv
from PIL import Image

# Load server-side credentials from .env.local (falls back to .env).
# `override=False` means real environment variables win over the file.
_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, ".env.local"), override=False)
load_dotenv(os.path.join(_HERE, ".env"), override=False)

import higgsfield_client as hf
from higgsfield_client.exceptions import CredentialsMissedError, HiggsfieldClientError

MODEL = "bytedance/seedance-2.5/image-to-video"
PLACEHOLDER_KEY = "YOUR_KEY_ID:YOUR_KEY_SECRET"

st.set_page_config(page_title="Seedance 2.5 — Image to Video", page_icon="🎬", layout="wide")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def credentials_ready() -> bool:
    """True when a non-placeholder HF_KEY (or HF_API_KEY/SECRET) is present."""
    key = os.getenv("HF_KEY", "").strip()
    if key and key != PLACEHOLDER_KEY:
        return True
    if os.getenv("HF_API_KEY") and os.getenv("HF_API_SECRET"):
        return True
    return False


def upload_reference(file) -> str:
    """Upload an uploaded image file to Higgsfield and return its hosted URL."""
    data = file.getvalue()
    content_type = getattr(file, "type", None) or mimetypes.guess_type(file.name)[0]
    try:
        return hf.upload(data, content_type or "image/png")
    except Exception:
        # Fall back to re-encoding via PIL if the raw upload is rejected.
        image = Image.open(io.BytesIO(data)).convert("RGB")
        return hf.upload_image(image, format="jpeg")


def extract_video_url(result) -> str | None:
    """Pull the generated video URL out of the SDK's JSON response."""
    if not isinstance(result, dict):
        return None
    video = result.get("video")
    if isinstance(video, str):
        return video
    if isinstance(video, dict):
        return video.get("url") or video.get("video_url")
    # Some responses nest the file under other keys — probe common ones.
    for key in ("video_url", "url", "output", "result"):
        val = result.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
        if isinstance(val, dict) and isinstance(val.get("url"), str):
            return val["url"]
    return None


# --------------------------------------------------------------------------- #
# Sidebar — generation parameters
# --------------------------------------------------------------------------- #
st.sidebar.title("⚙️ Parameters")
st.sidebar.caption(f"Model: `{MODEL}`")

resolution = st.sidebar.selectbox("Resolution", ["720p", "480p"], index=0)
duration = st.sidebar.slider("Duration (seconds)", min_value=4, max_value=30, value=5)
output_format = st.sidebar.selectbox("Output format", ["mp4", "mov"], index=0)
generate_audio = st.sidebar.checkbox("Generate audio", value=True)

st.sidebar.divider()
if credentials_ready():
    st.sidebar.success("Higgsfield credentials loaded.")
else:
    st.sidebar.error("HF_KEY not configured.")
    st.sidebar.caption(
        "Add your key to `.env.local` as `HF_KEY=KEY_ID:KEY_SECRET`, "
        "then restart the app."
    )


# --------------------------------------------------------------------------- #
# Main — inputs
# --------------------------------------------------------------------------- #
st.title("🎬 Seedance 2.5 — Image to Video")
st.write(
    "Generate a video from a reference image using the Higgsfield API. "
    "Upload a start image (required), optionally add a prompt and an end image, "
    "then generate."
)

col_start, col_end = st.columns(2)

with col_start:
    st.subheader("Start image (required)")
    start_source = st.radio(
        "Source", ["Upload", "Image URL"], horizontal=True, key="start_source"
    )
    start_file = None
    start_url_input = ""
    if start_source == "Upload":
        start_file = st.file_uploader(
            "Reference image", type=["png", "jpg", "jpeg", "webp"], key="start_upload"
        )
        if start_file:
            st.image(start_file, caption="Start image", use_container_width=True)
    else:
        start_url_input = st.text_input("Start image URL", key="start_url")
        if start_url_input:
            st.image(start_url_input, caption="Start image", use_container_width=True)

with col_end:
    st.subheader("End image (optional)")
    end_source = st.radio(
        "Source", ["None", "Upload", "Image URL"], horizontal=True, key="end_source"
    )
    end_file = None
    end_url_input = ""
    if end_source == "Upload":
        end_file = st.file_uploader(
            "End image", type=["png", "jpg", "jpeg", "webp"], key="end_upload"
        )
        if end_file:
            st.image(end_file, caption="End image", use_container_width=True)
    elif end_source == "Image URL":
        end_url_input = st.text_input("End image URL", key="end_url")
        if end_url_input:
            st.image(end_url_input, caption="End image", use_container_width=True)

prompt = st.text_area(
    "Prompt (optional)",
    placeholder="Describe the motion or scene, e.g. 'slow cinematic zoom, gentle camera pan'",
    height=90,
)

generate = st.button("🎥 Generate video", type="primary", use_container_width=True)


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
if generate:
    if not credentials_ready():
        st.error(
            "Higgsfield credentials are not configured. Set `HF_KEY` in "
            "`.env.local` (format `KEY_ID:KEY_SECRET`) and restart."
        )
        st.stop()

    has_start = bool(start_file) or bool(start_url_input.strip())
    if not has_start:
        st.error("A start image is required — upload one or provide an image URL.")
        st.stop()

    try:
        with st.status("Preparing request…", expanded=True) as status:
            # Resolve the start image URL (upload if a file was provided).
            if start_file:
                status.update(label="Uploading start image…")
                image_url = upload_reference(start_file)
            else:
                image_url = start_url_input.strip()

            # Resolve optional end image URL.
            end_image_url = None
            if end_file:
                status.update(label="Uploading end image…")
                end_image_url = upload_reference(end_file)
            elif end_url_input.strip():
                end_image_url = end_url_input.strip()

            arguments = {
                "image_url": image_url,
                "duration": duration,
                "resolution": resolution,
                "output_format": output_format,
                "generate_audio": generate_audio,
            }
            if prompt.strip():
                arguments["prompt"] = prompt.strip()
            if end_image_url:
                arguments["end_image_url"] = end_image_url

            def on_enqueue(request_id: str) -> None:
                status.update(label=f"Queued (request {request_id})…")

            def on_queue_update(current) -> None:
                status.update(label=f"Processing… ({type(current).__name__})")

            status.update(label="Submitting to Seedance 2.5…")
            result = hf.subscribe(
                MODEL,
                arguments=arguments,
                on_enqueue=on_enqueue,
                on_queue_update=on_queue_update,
            )
            status.update(label="Done!", state="complete")

        video_url = extract_video_url(result)
        if video_url:
            st.success("Video generated.")
            st.video(video_url)
            st.markdown(f"[⬇️ Open / download video]({video_url})")
        else:
            st.warning("Request completed but no video URL was found in the response.")

        with st.expander("Raw API response"):
            st.json(result)

    except CredentialsMissedError:
        st.error(
            "Higgsfield credentials missing or invalid. Check `HF_KEY` in `.env.local`."
        )
    except HiggsfieldClientError as exc:
        st.error(f"Higgsfield API error: {exc}")
    except Exception as exc:  # noqa: BLE001 — surface any failure to the user
        st.error(f"Generation failed: {exc}")
