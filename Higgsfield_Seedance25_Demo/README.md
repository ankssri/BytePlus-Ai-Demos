# Seedance 2.5 — Image to Video (Higgsfield)

A Streamlit web app that generates videos from a reference image using the
[Higgsfield API](https://higgsfield.ai/) with the **Seedance 2.5**
image-to-video model (`bytedance/seedance-2.5/image-to-video`), via the
official [`higgsfield-client`](https://pypi.org/project/higgsfield-client/)
Python SDK.

## Features

- Upload a **start image** (or paste an image URL) — required.
- Optional **end image**, **prompt**, and **audio generation**.
- Configurable **resolution** (480p / 720p), **duration** (4–30s), and
  **output format** (mp4 / mov).
- Uploaded images are hosted through the SDK's `upload` helper, so you only
  need a local file — no external image host required.
- Live progress status and inline video playback with a download link.

## Prerequisites

- Python 3.9+
- A Higgsfield API key from <https://cloud.higgsfield.ai/> in
  `KEY_ID:KEY_SECRET` format.

## Setup

```bash
cd Higgsfield_Seedance25_Demo
python -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt
```

### Configure credentials

Copy the example file and add your key. `.env.local` is git-ignored — the key
stays on your machine and is never committed.

```bash
cp .env.local.example .env.local
```

Then edit `.env.local`:

```
HF_KEY=your_key_id:your_key_secret
```

Credentials are loaded at runtime and read directly from the environment by the
SDK. This app never prints, logs, or commits the key.

## Run

```bash
streamlit run app.py
```

Open the URL Streamlit prints (default <http://localhost:8501>), upload a
reference image, adjust parameters in the sidebar, and click **Generate video**.

## How it works

1. The start image is uploaded via `higgsfield_client.upload(...)`, returning a
   hosted URL.
2. Parameters are sent to `higgsfield_client.subscribe(MODEL, arguments=...)`,
   which submits the request and polls until the video is ready.
3. The completed response's `video` field is played back inline.

## Request parameters (Seedance 2.5)

| Parameter        | Type    | Required | Default  | Notes                    |
| ---------------- | ------- | -------- | -------- | ------------------------ |
| `image_url`      | string  | Yes      | —        | Start / reference image  |
| `prompt`         | string  | No       | —        | Min length 1             |
| `duration`       | integer | No       | 5        | Min 4, max 30            |
| `resolution`     | string  | No       | `720p`   | `480p`, `720p`           |
| `end_image_url`  | string  | No       | —        | Optional final frame     |
| `output_format`  | string  | No       | `mp4`    | `mp4`, `mov`             |
| `generate_audio` | boolean | No       | `true`   | Add generated audio      |

## Security notes

- Keep `HF_KEY` server-side. Never expose it in browser code or commit it.
- `.env`, `.env.local`, and `.env.*.local` are git-ignored by this project.
