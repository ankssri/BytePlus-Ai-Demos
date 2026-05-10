# Seedance 2.0 Real-Human Portrait Video Demo

A Flask web application demonstrating the full BytePlus ModelArk **Private Real-Human Portrait Library** workflow — from signing the authorization letter and registering face/video/audio assets through to watching the AI-generated video in the browser.

---

## What It Does

The app walks through five steps:

1. **Asset Group** — Create or select a `LivenessFace` asset group
2. **Register Assets** — Upload Image, Video, or Audio assets (multiple per group)
3. **Write Prompt** — Reference assets positionally (`Image 1`, `Video 1`, `Audio 1`)
4. **Generate Video** — Submit a Seedance 2.0 task; optionally enable AI audio generation
5. **Watch Result** — Play and download the generated MP4

An **API Request Inspector** panel shows the exact JSON sent and received at every step.

---

## Key Differences from the Virtual Portrait Demo

| Feature | Virtual Portrait Demo | Real-Human Portrait Demo |
|---------|----------------------|--------------------------|
| `GroupType` | `AIGC` | `LivenessFace` |
| Authorization letter | Not required | **Required** in console before first group |
| Asset types | Image only | Image, Video, Audio |
| Multi-asset in one video | Single image | Up to multiple assets positionally referenced |
| `generate_audio` field | Not used | Supported (`true` / `false`) |
| Max duration | 10 s | 11 s |

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Python | 3.9 or later |
| **Authorization letter** | Sign in BytePlus Console → My assets → Real-Human Portrait → Manage assets (one-time) |
| **ARK_API_KEY** | BytePlus Console → API Keys — used for video generation (Bearer token) |
| **ARK_AK** | BytePlus Console → Access Keys → Access Key ID — used for asset library APIs |
| **ARK_SK** | BytePlus Console → Access Keys → Secret Access Key — used for asset library APIs |
| Asset URLs | Publicly accessible HTTPS URLs for your portrait images/videos/audio |

> Both credential sets are required. The asset library and video generation APIs use different hosts and auth schemes.

---

## Quickstart

### 1. Clone the repository

```bash
git clone https://github.com/ankssri/BytePlus-Ai-Demos.git
cd BytePlus-Ai-Demos/RealHuman_Portrait_Demo
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate      # macOS / Linux
# venv\Scripts\activate       # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your credentials:

```env
ARK_API_KEY=your_api_key_here
ARK_AK=your_access_key_id_here
ARK_SK=your_secret_access_key_here
SEEDANCE_MODEL_ID=dreamina-seedance-2-0-260128
PORT=5051
FLASK_DEBUG=true
```

### 5. Run the app

```bash
python app.py
```

Open your browser at **http://localhost:5051**

---

## Project Structure

```
RealHuman_Portrait_Demo/
├── app.py               # Flask backend — all BytePlus API routes
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
├── WORKFLOW_GUIDE.md    # Detailed API reference with request/response examples
├── CLAUDE.md            # Architecture context for Claude Code sessions
├── templates/
│   └── index.html       # Single-page UI
└── static/
    ├── css/style.css
    └── js/app.js        # Frontend workflow logic
```

---

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/config` | Check which credentials are configured |
| `POST` | `/api/start-verify-session` | Start H5 liveness verification session (HMAC-SHA256) |
| `POST` | `/api/get-group-from-token` | Get GroupId from BytedToken after verification (HMAC-SHA256) |
| `GET` | `/verify-callback` | Callback page — receives BytedToken from H5 redirect |
| `GET` | `/api/list-asset-groups` | List existing LivenessFace groups (HMAC-SHA256) |
| `POST` | `/api/create-asset` | Register an asset URL (Image/Video/Audio) (HMAC-SHA256) |
| `GET` | `/api/asset-status/<id>` | Poll asset verification status (HMAC-SHA256) |
| `GET` | `/api/list-assets?group_id=<id>` | List assets in a group (HMAC-SHA256) |
| `POST` | `/api/create-video-task` | Submit a Seedance 2.0 generation task (Bearer) |
| `GET` | `/api/video-task/<id>` | Poll video generation task status (Bearer) |

---

## Prompt Format

Reference registered assets by **type + position** — never by Asset ID:

```
The person in Image 1 wearing the outfit from Image 2 presents a product with a bright smile.
Voice style from Audio 1. --ratio 9:16 --resolution 1080p --duration 11
```

| Reference | Description |
|-----------|-------------|
| `Image 1` | First image asset in the request |
| `Image 2` | Second image asset |
| `Video 1` | First video asset |
| `Audio 1` | First audio asset |

Assets are indexed **per type** — images and audio are numbered independently.

| Flag | Values | Default |
|------|--------|---------|
| `--ratio` | `16:9` `9:16` `1:1` `4:3` `3:4` | — |
| `--resolution` | `720p` `1080p` | — |
| `--duration` | `5` `10` `11` | — |

---

## Model IDs

| Model | ID |
|-------|----|
| Seedance 2.0 Standard | `dreamina-seedance-2-0-260128` |
| Seedance 2.0 Fast | `dreamina-seedance-2-0-fast-260128` |
| Custom endpoint | `ep-xxxx` |

---

## Troubleshooting

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `AccessDenied` on CreateAssetGroup | Authorization letter not signed | Sign in console: My assets → Real-Human Portrait → Manage assets |
| `AK/SK Missing ⚠` in header | `ARK_AK` or `ARK_SK` not set in `.env` | Add both and restart |
| Asset stuck in `Processing` | Image URL not publicly accessible | Ensure URL works without authentication |
| `MissingParameter.Filter` | Outdated code | Pull latest from `main` |
| Video URL not loading | CDN link expired (12-hour validity) | Download promptly |
| `Moderation.Strategy: Skip` error | Secure Mode still on | Disable Secure Mode in console first (irreversible) |

---

## Further Reading

- [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md) — full API reference with Python examples
- [BytePlus Private Asset Library Docs](https://docs.byteplus.com/en/docs/ModelArk/2333565)
- [Seedance 2.0 API Reference](https://docs.byteplus.com/en/docs/ModelArk/1520757)
