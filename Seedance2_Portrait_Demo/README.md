# Seedance 2.0 Portrait Video Demo

A Flask web application that demonstrates the full BytePlus ModelArk **Seedance 2.0** portrait video generation workflow — from registering a face image in the Private Asset Library through to watching the generated video in the browser.

---

## What It Does

The app walks through five steps:

1. **Provide Portrait URL** — paste a publicly accessible HTTPS link to a face image
2. **Register Asset** — create (or reuse) an asset group and register the image in BytePlus's Private Asset Library
3. **Write Prompt** — describe the video scene; append `--ratio`, `--resolution`, `--duration` for output settings
4. **Generate Video** — submit a Seedance 2.0 generation task and poll until complete
5. **Watch Result** — play and download the generated MP4

An **API Request Inspector** panel shows the exact JSON sent and received at every step.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Python | 3.9 or later |
| **ARK_API_KEY** | BytePlus ModelArk Console → **API Keys** — used for video generation (Bearer token) |
| **ARK_AK** | BytePlus Console → **Access Keys** → Access Key ID — used for asset library APIs (HMAC-SHA256) |
| **ARK_SK** | BytePlus Console → **Access Keys** → Secret Access Key — used for asset library APIs (HMAC-SHA256) |
| Public image URL | A publicly accessible HTTPS URL to a face portrait image (min 300×300 px) |

> The asset library APIs (`CreateAssetGroup`, `CreateAsset`, `GetAsset`, `ListAssetGroups`) use a different host and authentication scheme from the video generation API. Both sets of credentials are required.

---

## Quickstart

### 1. Clone the repository

```bash
git clone https://github.com/ankssri/BytePlus-Ai-Demos.git
cd BytePlus-Ai-Demos/Seedance2_Portrait_Demo
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
# Video Generation API (Bearer token)
ARK_API_KEY=your_api_key_here

# Asset Library APIs (HMAC-SHA256 AK/SK)
ARK_AK=your_access_key_id_here
ARK_SK=your_secret_access_key_here

# Model ID — use built-in or your custom inference endpoint
SEEDANCE_MODEL_ID=dreamina-seedance-2-0-260128

# Server
PORT=5050
FLASK_DEBUG=true
```

### 5. Run the app

```bash
python app.py
```

Open your browser at **http://localhost:5050**

---

## Project Structure

```
Seedance2_Portrait_Demo/
├── app.py               # Flask backend — all BytePlus API routes
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
├── WORKFLOW_GUIDE.md    # Detailed step-by-step API reference
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
| `GET` | `/api/list-asset-groups` | List existing asset groups (HMAC-SHA256) |
| `POST` | `/api/create-asset-group` | Create a new asset group (HMAC-SHA256) |
| `POST` | `/api/create-asset` | Register an image URL as an asset (HMAC-SHA256) |
| `GET` | `/api/asset-status/<id>` | Poll asset verification status (HMAC-SHA256) |
| `POST` | `/api/create-video-task` | Submit a Seedance 2.0 generation task (Bearer) |
| `GET` | `/api/video-task/<id>` | Poll video generation task status (Bearer) |

---

## Prompt Format

Write your prompt naturally. Append output settings as inline flags — the backend extracts them automatically:

```
A confident person walks through a sunlit Tokyo street, cinematic tracking shot --ratio 16:9 --resolution 1080p --duration 5
```

| Flag | Values | Default |
|------|--------|---------|
| `--ratio` | `16:9` `9:16` `1:1` `4:3` `3:4` | — |
| `--resolution` | `720p` `1080p` | — |
| `--duration` | `5` `10` | — |

---

## Model IDs

| Model | ID | Notes |
|-------|----|-------|
| Seedance 2.0 Standard | `dreamina-seedance-2-0-260128` | Default |
| Seedance 2.0 Fast | `dreamina-seedance-2-0-fast-260128` | Lower cost, faster |
| Custom endpoint | `ep-xxxx` | Your inference endpoint ID from the console |

---

## Troubleshooting

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `AK/SK Missing ⚠` in header badge | `ARK_AK` or `ARK_SK` not set in `.env` | Add both to `.env` and restart |
| `MissingParameter.Filter` | Outdated code | Pull latest from `main` |
| `AccessDenied` on video task | Model/endpoint ID not accessible to your API key | Check endpoint access in ModelArk console |
| Asset stuck in `Processing` | Image URL not publicly reachable | Ensure the URL is accessible without authentication |
| Video URL not loading | CDN link has expired | BytePlus CDN links expire — download promptly |

---

## Further Reading

- [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md) — complete API reference with request/response examples and Python code
- [BytePlus ModelArk Docs](https://docs.byteplus.com/en/docs/ModelArk/2333565)
- [Seedance 2.0 API Reference](https://docs.byteplus.com/en/docs/ModelArk/1520757)
