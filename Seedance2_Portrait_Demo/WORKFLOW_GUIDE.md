# BytePlus ModelArk — Seedance 2.0 Portrait Video Workflow Guide

A step-by-step guide to upload a face image, register it in the Private Trusted Asset Library, and generate a video with Seedance 2.0.

---

## Overview

The full workflow has two parallel tracks that converge at video generation:

```
[User uploads face image]
        │
        ▼
[Step 1] CreateAssetGroup  ──→  group_id
        │
        ▼
[Step 2] CreateAsset (upload image)  ──→  asset_id  ──┐
                                                       │
[User writes video prompt] ────────────────────────────┤
                                                       ▼
                                          [Step 3] Create Video Task
                                                  (model + prompt + asset)
                                                       │
                                                       ▼
                                          [Step 4] Poll Task Status
                                                       │
                                                  status == "succeeded"
                                                       │
                                                       ▼
                                          [Step 5] Display Video URL
```

The asset registration (Steps 1–2) can happen in the background while the user composes their prompt.

---

## Prerequisites

| Item | Details |
|------|---------|
| BytePlus API Key | Obtain from the ModelArk console → **API Keys** |
| Seedance 2.0 Model ID | `dreamina-seedance-2-0-260128` (standard) or `dreamina-seedance-2-0-fast-260128` (fast), or your custom endpoint ID `ep-xxxx` |
| Face image | Front-facing close-up, neutral expression, face occupying ~2/3 of frame, min 300×300px, max 6000×6000px, aspect ratio 0.4–2.5 |
| Public image URL | Host the face image at a publicly accessible URL (BytePlus TOS recommended) **or** encode it as a base64 data URI |

### Authentication

Every API call uses the same Bearer token header:

```http
Authorization: Bearer <YOUR_ARK_API_KEY>
Content-Type: application/json
```

**Base URL**: `https://ark.ap-southeast.bytepluses.com/api/v3`

---

## Step 1 — Create an Asset Group

Asset groups are named containers that organise your trusted portrait assets.

**Reference**: [CreateAssetGroup API](https://docs.byteplus.com/en/docs/ModelArk/2318270)

### Request

```http
POST https://ark.ap-southeast.bytepluses.com/api/v3/assets/groups
Authorization: Bearer <YOUR_ARK_API_KEY>
Content-Type: application/json
```

```json
{
  "name": "My Portrait Group",
  "description": "Trusted face assets for Seedance 2.0 video generation"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Display name for the asset group |
| `description` | string | No | Optional description |

### Response

```json
{
  "id": "assetgrp-20250510-abc123",
  "name": "My Portrait Group",
  "description": "Trusted face assets for Seedance 2.0 video generation",
  "created_at": 1746786000,
  "updated_at": 1746786000
}
```

| Field | Description |
|-------|-------------|
| `id` | **Save this `group_id`** — used in Step 2 |
| `name` | Group display name |
| `created_at` | Unix timestamp |

---

## Step 2 — Upload a Portrait Asset

Upload the face image to the group. The asset enters a verification queue; once verified its status becomes `active`.

**Reference**: [CreateAsset API](https://docs.byteplus.com/en/docs/ModelArk/2318271)

### Request

```http
POST https://ark.ap-southeast.bytepluses.com/api/v3/assets
Authorization: Bearer <YOUR_ARK_API_KEY>
Content-Type: application/json
```

```json
{
  "group_id": "assetgrp-20250510-abc123",
  "name": "Alice Portrait",
  "content_type": "image",
  "url": "https://your-tos-bucket.tos-ap-southeast-1.bytepluses.com/alice_face.jpg"
}
```

> **Tip**: You can also pass a base64-encoded image as the `url` field using the data URI format:
> `"url": "data:image/jpeg;base64,/9j/4AAQ..."`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `group_id` | string | Yes | ID returned by CreateAssetGroup |
| `name` | string | Yes | Display name for this asset |
| `content_type` | string | Yes | `"image"` for portrait photos |
| `url` | string | Yes | Publicly accessible image URL or base64 data URI |

### Response

```json
{
  "id": "asset-20250510-xyz789",
  "group_id": "assetgrp-20250510-abc123",
  "name": "Alice Portrait",
  "content_type": "image",
  "status": "pending",
  "created_at": 1746786120,
  "updated_at": 1746786120
}
```

| Field | Description |
|-------|-------------|
| `id` | **Save this `asset_id`** — used in Step 3 |
| `status` | `pending` → `processing` → `active` (or `failed`) |

### Polling Asset Status

Poll `GET /api/v3/assets/{asset_id}` until `status == "active"` before generating a video.

```http
GET https://ark.ap-southeast.bytepluses.com/api/v3/assets/asset-20250510-xyz789
Authorization: Bearer <YOUR_ARK_API_KEY>
```

```json
{
  "id": "asset-20250510-xyz789",
  "status": "active",
  ...
}
```

---

## Step 3 — Create a Video Generation Task

Submit the video generation request, referencing the verified portrait asset.

**Reference**: [Seedance 2.0 Video Generation API](https://docs.byteplus.com/en/docs/ModelArk/1520757)

### Request

```http
POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks
Authorization: Bearer <YOUR_ARK_API_KEY>
Content-Type: application/json
```

#### Option A — Using the Asset URI (Trusted Asset Library)

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "content": [
    {
      "type": "text",
      "text": "A confident woman walks through a sunlit Tokyo street, cinematic tracking shot --ratio 16:9 --resolution 1080p --duration 5"
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "asset://asset-20250510-xyz789"
      },
      "role": "reference_image"
    }
  ]
}
```

#### Option B — Using a Direct Image URL (I2V without asset library)

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "content": [
    {
      "type": "text",
      "text": "A person walks through a beautiful garden, photorealistic --ratio 16:9 --resolution 720p --duration 5"
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "https://your-tos-bucket.tos-ap-southeast-1.bytepluses.com/face.jpg"
      },
      "role": "reference_image"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `model` | string | Seedance 2.0 model ID or your custom endpoint ID (`ep-xxxx`) |
| `content` | array | Array of content objects (text + image) |
| `content[].type` | string | `"text"` or `"image_url"` |
| `content[].text` | string | The video generation prompt (text type only) |
| `content[].image_url.url` | string | Image URL, base64 data URI, or `asset://{asset_id}` |
| `content[].role` | string | `"reference_image"` for face portrait, `"first_frame"` for start frame |

#### Prompt Inline Parameters

Append these flags directly in your text prompt:

| Flag | Example | Description |
|------|---------|-------------|
| `--ratio` | `--ratio 16:9` | Aspect ratio (`16:9`, `9:16`, `1:1`, `4:3`, `3:4`) |
| `--resolution` | `--resolution 1080p` | Output resolution (`720p`, `1080p`) |
| `--duration` | `--duration 5` | Video duration in seconds (`5` or `10`) |

### Response

```json
{
  "id": "task-20250510-def456",
  "status": "queued",
  "model": "dreamina-seedance-2-0-260128",
  "created_at": 1746786300
}
```

| Field | Description |
|-------|-------------|
| `id` | **Save this `task_id`** — used in Step 4 |
| `status` | Initial status: `"queued"` |

---

## Step 4 — Poll for Task Completion

Poll the task endpoint every 5–10 seconds until `status` is `"succeeded"` or `"failed"`.

**Reference**: [Retrieve Video Generation Task](https://docs.byteplus.com/en/docs/ModelArk/1521309)

### Request

```http
GET https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks/task-20250510-def456
Authorization: Bearer <YOUR_ARK_API_KEY>
```

### Response — Still Running

```json
{
  "id": "task-20250510-def456",
  "status": "running",
  "model": "dreamina-seedance-2-0-260128",
  "created_at": 1746786300,
  "updated_at": 1746786360
}
```

### Response — Succeeded

```json
{
  "id": "task-20250510-def456",
  "status": "succeeded",
  "model": "dreamina-seedance-2-0-260128",
  "created_at": 1746786300,
  "updated_at": 1746786600,
  "content": {
    "video_url": "https://cdn-ark.byteplus.com/generated/task-20250510-def456/output.mp4"
  }
}
```

### Response — Failed

```json
{
  "id": "task-20250510-def456",
  "status": "failed",
  "error": {
    "code": "InvalidInput",
    "message": "Reference image does not meet portrait requirements."
  }
}
```

| `status` value | Meaning |
|----------------|---------|
| `queued` | Task is waiting in queue |
| `running` | Video is being generated |
| `succeeded` | Generation complete — `content.video_url` has the download link |
| `failed` | Generation failed — check `error.message` |

Typical generation time: **2–5 minutes**.

---

## Step 5 — Download and Display the Video

```http
GET <content.video_url>
```

The URL is a direct MP4 link. In a browser you can embed it with an HTML `<video>` tag or provide a download link.

---

## Complete Python Example

```python
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
API_KEY  = os.getenv("ARK_API_KEY")
MODEL_ID = os.getenv("SEEDANCE_MODEL_ID", "dreamina-seedance-2-0-260128")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


# ---------- Step 1: Create Asset Group ----------
def create_asset_group(name: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/assets/groups",
        headers=HEADERS,
        json={"name": name, "description": "Portrait assets for Seedance 2.0"},
    )
    resp.raise_for_status()
    group_id = resp.json()["id"]
    print(f"Asset group created: {group_id}")
    return group_id


# ---------- Step 2: Upload Portrait Asset ----------
def create_asset(group_id: str, name: str, image_url: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/assets",
        headers=HEADERS,
        json={
            "group_id": group_id,
            "name": name,
            "content_type": "image",
            "url": image_url,
        },
    )
    resp.raise_for_status()
    asset_id = resp.json()["id"]
    print(f"Asset created: {asset_id}")
    return asset_id


def wait_for_asset(asset_id: str, timeout: int = 120) -> bool:
    """Poll until asset status is 'active'."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{BASE_URL}/assets/{asset_id}", headers=HEADERS)
        resp.raise_for_status()
        status = resp.json().get("status")
        print(f"  Asset status: {status}")
        if status == "active":
            return True
        if status == "failed":
            return False
        time.sleep(5)
    raise TimeoutError("Asset verification timed out")


# ---------- Step 3: Create Video Task ----------
def create_video_task(prompt: str, asset_id: str) -> str:
    payload = {
        "model": MODEL_ID,
        "content": [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"asset://{asset_id}"},
                "role": "reference_image",
            },
        ],
    }
    resp = requests.post(
        f"{BASE_URL}/contents/generations/tasks",
        headers=HEADERS,
        json=payload,
    )
    resp.raise_for_status()
    task_id = resp.json()["id"]
    print(f"Video task created: {task_id}")
    return task_id


# ---------- Step 4: Poll Task ----------
def wait_for_video(task_id: str, timeout: int = 600) -> str:
    """Poll until task succeeds; return the video URL."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{BASE_URL}/contents/generations/tasks/{task_id}",
            headers=HEADERS,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        print(f"  Task status: {status}")
        if status == "succeeded":
            return data["content"]["video_url"]
        if status == "failed":
            raise RuntimeError(f"Task failed: {data.get('error')}")
        time.sleep(10)
    raise TimeoutError("Video generation timed out")


# ---------- Main ----------
if __name__ == "__main__":
    # Your publicly accessible face image URL (or base64 data URI)
    face_image_url = "https://your-tos-bucket.tos-ap-southeast-1.bytepluses.com/alice_face.jpg"
    prompt = (
        "Alice walks confidently through a modern city at golden hour, "
        "cinematic tracking shot --ratio 16:9 --resolution 1080p --duration 5"
    )

    group_id = create_asset_group("My Portraits")
    asset_id = create_asset(group_id, "Alice", face_image_url)

    print("Waiting for asset verification...")
    if not wait_for_asset(asset_id):
        raise RuntimeError("Asset verification failed")

    task_id = create_video_task(prompt, asset_id)

    print("Waiting for video generation...")
    video_url = wait_for_video(task_id)
    print(f"\nVideo ready: {video_url}")
```

---

## Error Codes

| HTTP Status | Error Code | Meaning | Action |
|-------------|-----------|---------|--------|
| 400 | `InvalidInput` | Bad request parameters | Check prompt length, image format, aspect ratio |
| 401 | `AuthError` | Invalid or missing API key | Verify `ARK_API_KEY` value |
| 403 | `PermissionDenied` | Asset not verified or model not accessible | Wait for asset `active` status; check model access |
| 429 | `RateLimitExceeded` | Too many requests | Implement exponential back-off |
| 500 | `InternalError` | Server-side error | Retry with back-off |

---

## Image Requirements for Portrait Assets

| Parameter | Requirement |
|-----------|-------------|
| Framing | Front-facing close-up, face fills ~2/3 of frame |
| Expression | Neutral, no extreme expressions |
| Crop | Head and shoulders visible |
| Minimum size | 300 × 300 px |
| Maximum size | 6000 × 6000 px |
| Aspect ratio | 0.4 – 2.5 |
| Formats | JPEG, JPG, PNG, WEBP, BMP, TIFF |

---

## References

- [Private Virtual Portrait Library Overview](https://docs.byteplus.com/en/docs/ModelArk/2333565)
- [Add Real-Human Assets to Asset Library](https://docs.byteplus.com/en/docs/ModelArk/2315856)
- [CreateAssetGroup API](https://docs.byteplus.com/en/docs/ModelArk/2318270)
- [CreateAsset API](https://docs.byteplus.com/en/docs/ModelArk/2318271)
- [Seedance 2.0 Video Generation API](https://docs.byteplus.com/en/docs/ModelArk/1520757)
- [Retrieve Video Generation Task](https://docs.byteplus.com/en/docs/ModelArk/1521309)
- [Dreamina Seedance 2.0 Series Tutorial](https://docs.byteplus.com/api/docs/ModelArk/2291680)
