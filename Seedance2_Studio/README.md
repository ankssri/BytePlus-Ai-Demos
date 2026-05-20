# Seedance 2.0 Studio

A workflow-oriented video generation demo built on **BytePlus ModelArk** Asset Library + Seedance 2.0 APIs.

While the sibling project `Seedance2_Portrait_Demo` is structured to teach customers *what* asset groups and assets are (step-by-step API walkthrough), **Studio is the next step**: a Higgsfield-style creative interface that combines a text prompt with image / video / audio references — all pulled from the Asset Library — and submits them to Seedance 2.0 as a single multimodal generation.

## Features

- **Asset Library browser** (left rail)
  - Lists *all* asset groups (server-side pagination, no 50-item cap)
  - Filters by asset type: Image / Video / Audio
  - Inline previews: thumbnails for images, hover-to-play for videos, hover popover for audio
  - Search by name or ID
  - Click an asset to attach it to the matching reference slot

- **Composer** (center)
  - Prompt textarea (supports inline `--ratio`, `--duration`, `--resolution` flags)
  - Three reference slots (image / video / audio) — populate by click or drag-drop, or paste a public URL directly
  - Ratio / Duration / Resolution selectors
  - Inline video player for the generated output
  - Collapsible API Request Inspector (raw request + response)

- **History** (right rail)
  - Last 30 generations, persisted to `localStorage`
  - Live polling for in-flight tasks (resumes across page reloads)
  - Click a thumbnail to replay in the main output panel

## Architecture

Two auth schemes, same as `Seedance2_Portrait_Demo`:

| Surface         | Host                                   | Auth                  |
| --------------- | -------------------------------------- | --------------------- |
| Asset library   | `ark.ap-southeast-1.byteplusapi.com`   | HMAC-SHA256 AK/SK     |
| Video gen + poll| `ark.ap-southeast.bytepluses.com`      | Bearer API key        |

Backend endpoints (`app.py`):

| Method | Path                                  | Purpose                                  |
| ------ | ------------------------------------- | ---------------------------------------- |
| GET    | `/api/config`                         | Health/credential status                 |
| GET    | `/api/groups`                         | List all asset groups (auto-paginated)   |
| GET    | `/api/groups/<id>/assets?type=Image`  | List assets in a group, optional filter  |
| GET    | `/api/asset/<id>`                     | Get one asset                            |
| POST   | `/api/generate`                       | Submit Seedance 2.0 multimodal task      |
| GET    | `/api/task/<task_id>`                 | Poll task status / fetch video URL       |

Generation payload supports up to three references in a single call:

```json
{
  "prompt": "A woman walks through neon-lit Tokyo at night",
  "references": [
    { "type": "Image", "asset_id": "asset-abc..." },
    { "type": "Audio", "asset_id": "asset-xyz..." }
  ],
  "options": { "ratio": "16:9", "duration": 5, "resolution": "1080p" }
}
```

The backend translates each reference into the Seedance content-array form:
`image_url + role=reference_image`, `video_url + role=reference_video`, `audio_url + role=reference_audio`, using `asset://<id>` URIs when the reference came from the Asset Library.

## Setup

```bash
cd Seedance2_Studio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and fill in ARK_API_KEY, ARK_AK, ARK_SK

python app.py
# → http://localhost:5051
```

`SEEDANCE_MODEL_ID` defaults to `dreamina-seedance-2-0-260128` — override in `.env` if you have access to a different model id.

## Demo flow

1. The left rail loads all your existing asset groups. Pick one.
2. Filter to Image / Video / Audio with the pills, or search by name.
3. Click an asset — it snaps into the matching reference slot in the center.
4. Type a prompt, choose ratio/duration/resolution, hit **Generate Video**.
5. The task is polled every 4s. As soon as the video URL comes back, it auto-plays in the Output panel and lands as a thumbnail in the History rail.

## Notes

- Reference slots only accept matching types — dragging a Video onto the Image slot is rejected.
- You can also paste a raw public URL into any slot's text field if you don't want to upload to the Asset Library first.
- History is local-only (`localStorage`) — clearing browser data wipes it. Backend stores nothing.
