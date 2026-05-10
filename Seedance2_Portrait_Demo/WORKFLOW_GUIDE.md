# BytePlus ModelArk — Seedance 2.0 Portrait Video Workflow Guide

A step-by-step guide to register a face image in the Private Asset Library and generate a portrait video with Seedance 2.0.

---

## Architecture Overview

The workflow uses **two separate API systems** with different hosts and authentication:

| System | Host | Auth |
|--------|------|------|
| **Asset Library APIs** | `ark.ap-southeast-1.byteplusapi.com` | HMAC-SHA256 AK/SK signature |
| **Video Generation APIs** | `ark.ap-southeast.bytepluses.com` | Bearer API Key |

```
[Provide public face image URL]
        │
        ▼
[Step 1] CreateAssetGroup  ──→  Result.Id (group_id)
        │
        ▼
[Step 2] CreateAsset (public URL)  ──→  Result.Id (asset_id)
        │
        ▼
[Step 2b] Poll GetAsset  ──→  Result.Status == "Active"
        │
        ├──────────────────────────────────────────────────┐
[User writes video prompt]                                 │
        │                                                  │
        ▼                                                  │
[Step 3] Create Video Task  ←─ (asset://{asset_id}) ──────┘
        │
        ▼
[Step 4] Poll Task Status  ──→  status == "succeeded"
        │
        ▼
[Step 5] Display content.video_url
```

The asset registration (Steps 1–2b) runs in the background while the user writes their prompt.

> **Tip — reuse an existing group**: If you already have an asset group, you can skip Step 1 by calling `ListAssetGroups` (see below) to retrieve its ID, then go straight to Step 2.

---

## Prerequisites

| Item | How to Obtain |
|------|---------------|
| **ARK_API_KEY** | BytePlus ModelArk Console → API Keys (Bearer token for video APIs) |
| **ARK_AK** | BytePlus Console → Access Keys (Access Key ID for asset APIs) |
| **ARK_SK** | BytePlus Console → Access Keys (Secret Access Key for asset APIs) |
| **Seedance 2.0 Model ID** | `dreamina-seedance-2-0-260128` (standard) or `dreamina-seedance-2-0-fast-260128` (fast) |
| **Public face image URL** | A publicly accessible HTTPS URL to your portrait image — base64 is NOT supported by CreateAsset |

### Image Requirements

| Parameter | Requirement |
|-----------|-------------|
| Framing | Front-facing close-up, face fills ~2/3 of frame |
| Expression | Neutral, no extreme expressions |
| Minimum size | 300 × 300 px |
| Maximum size | 6000 × 6000 px |
| Aspect ratio | 0.4 – 2.5 |
| Formats | JPEG, PNG, WEBP, BMP, TIFF |

---

## Authentication

### Video APIs — Bearer Token

```http
Authorization: Bearer <ARK_API_KEY>
Content-Type: application/json
```

### Asset APIs — HMAC-SHA256 AK/SK Signature

Asset APIs use a signing scheme similar to AWS SigV4. The `Authorization` header has the form:

```
HMAC-SHA256 Credential=<AK>/<date>/<region>/<service>/request, SignedHeaders=content-type;host;x-content-sha256;x-date, Signature=<hex>
```

Additional required headers:

```http
X-Date: 20250510T120000Z        # UTC timestamp, format: YYYYMMDDTHHmmSSZ
X-Content-Sha256: <sha256hex>   # SHA-256 of the request body (lowercase hex)
Host: ark.ap-southeast-1.byteplusapi.com
```

See `app.py → _asset_signed_headers()` for the complete Python signing implementation.

---

## Step 0 (Optional) — List Existing Asset Groups

If you already have asset groups, retrieve them to find the ID you want to reuse.

### Request

```http
POST https://ark.ap-southeast-1.byteplusapi.com/?Action=ListAssetGroups&Version=2024-01-01
Authorization: HMAC-SHA256 Credential=<AK>/...
X-Date: <timestamp>
X-Content-Sha256: <body-sha256>
Host: ark.ap-southeast-1.byteplusapi.com
Content-Type: application/json
```

```json
{
  "Filter": {
    "GroupType": "AIGC"
  },
  "PageNumber": 1,
  "PageSize": 50,
  "SortBy": "CreateTime",
  "SortOrder": "Desc",
  "ProjectName": "default"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `Filter` | object | Yes | Filter conditions — must include at least `GroupType` |
| `Filter.GroupType` | string | Yes | `"AIGC"` for digital characters, `"LivenessFace"` for real-person portraits |
| `Filter.Name` | string | No | Filter by group name |
| `PageNumber` | integer | No | Page number, starting from 1 |
| `PageSize` | integer | No | Results per page, max 100 |
| `SortBy` | string | No | `"CreateTime"` (default) or `"UpdateTime"` |
| `SortOrder` | string | No | `"Desc"` (default) or `"Asc"` |

### Response

```json
{
  "ResponseMetadata": { ... },
  "Result": {
    "TotalCount": 2,
    "Items": [
      {
        "Id": "group-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "Name": "My Portrait Group",
        "Description": "Trusted face assets",
        "GroupType": "AIGC",
        "ProjectName": "default",
        "CreateTime": "2026-05-10T00:00:00Z",
        "UpdateTime": "2026-05-10T00:00:00Z"
      }
    ],
    "PageNumber": 1,
    "PageSize": 50
  }
}
```

**Extract**: `response["Result"]["Items"][n]["Id"]` — use this as your `group_id` and skip Step 1.

---

## Step 1 — Create an Asset Group

Asset groups are named containers that organise your trusted portrait assets.

### Request

```http
POST https://ark.ap-southeast-1.byteplusapi.com/?Action=CreateAssetGroup&Version=2024-01-01
Authorization: HMAC-SHA256 Credential=<AK>/...
X-Date: <timestamp>
X-Content-Sha256: <body-sha256>
Host: ark.ap-southeast-1.byteplusapi.com
Content-Type: application/json
```

```json
{
  "Name": "My Portrait Group",
  "Description": "Trusted face assets for Seedance 2.0 video generation",
  "GroupType": "AIGC",
  "ProjectName": "default"
}
```

> **Note**: Request body fields use **PascalCase** for all Asset Library APIs.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `Name` | string | Yes | Display name for the asset group |
| `Description` | string | No | Optional description |
| `GroupType` | string | Yes | Must be `"AIGC"` |
| `ProjectName` | string | Yes | Use `"default"` unless you have a specific project |

### Response

```json
{
  "ResponseMetadata": {
    "RequestId": "20250510120000...",
    "Action": "CreateAssetGroup",
    "Version": "2024-01-01",
    "Service": "ark",
    "Region": "ap-southeast-1"
  },
  "Result": {
    "Id": "group-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  }
}
```

**Extract**: `response["Result"]["Id"]` — this is your `group_id`.

---

## Step 2 — Create a Portrait Asset

Register the face image URL in the asset group. The image must be at a publicly accessible HTTPS URL — the API does **not** accept base64 data URIs.

### Request

```http
POST https://ark.ap-southeast-1.byteplusapi.com/?Action=CreateAsset&Version=2024-01-01
Authorization: HMAC-SHA256 Credential=<AK>/...
X-Date: <timestamp>
X-Content-Sha256: <body-sha256>
Host: ark.ap-southeast-1.byteplusapi.com
Content-Type: application/json
```

```json
{
  "GroupId": "group-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "URL": "https://example.com/alice_portrait.jpg",
  "AssetType": "Image",
  "Name": "Alice Portrait",
  "ProjectName": "default"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `GroupId` | string | Yes | ID returned by CreateAssetGroup |
| `URL` | string | Yes | Publicly accessible HTTPS image URL |
| `AssetType` | string | Yes | Must be `"Image"` |
| `Name` | string | Yes | Display name for this asset |
| `ProjectName` | string | Yes | Use `"default"` |

### Response

```json
{
  "ResponseMetadata": { ... },
  "Result": {
    "Id": "asset-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  }
}
```

**Extract**: `response["Result"]["Id"]` — this is your `asset_id`.

---

## Step 2b — Poll Asset Status

After creation the asset enters a verification queue. Poll `GetAsset` until `Status` is `"Active"`.

### Request

```http
POST https://ark.ap-southeast-1.byteplusapi.com/?Action=GetAsset&Version=2024-01-01
Authorization: HMAC-SHA256 Credential=<AK>/...
X-Date: <timestamp>
X-Content-Sha256: <body-sha256>
Host: ark.ap-southeast-1.byteplusapi.com
Content-Type: application/json
```

```json
{
  "Id": "asset-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "ProjectName": "default"
}
```

### Response

```json
{
  "ResponseMetadata": { ... },
  "Result": {
    "Id": "asset-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "Status": "Active",
    "Name": "Alice Portrait",
    "GroupId": "group-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  }
}
```

| `Status` value | Meaning |
|----------------|---------|
| `Processing` | Image is being verified by BytePlus |
| `Active` | Asset is verified and ready to use in video generation |
| `Failed` | Verification failed (check image requirements) |

Poll every 5 seconds; typical verification takes 10–30 seconds.

---

## Step 3 — Create a Video Generation Task

Submit the video generation request referencing the verified portrait asset.

### Request

```http
POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks
Authorization: Bearer <ARK_API_KEY>
Content-Type: application/json
```

#### Option A — Using the Asset URI (Recommended for portrait fidelity)

Reference your verified asset using the `asset://` URI scheme:

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "content": [
    {
      "type": "text",
      "text": "Alice walks confidently through a sunlit Tokyo street, cinematic tracking shot, photorealistic"
    },
    {
      "type": "image_url",
      "role": "reference_image",
      "image_url": {
        "url": "asset://asset-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
      }
    }
  ],
  "ratio": "16:9",
  "resolution": "1080p",
  "duration": 5,
  "watermark": false
}
```

#### Option B — Using a Direct Public Image URL (I2V without asset library)

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "content": [
    {
      "type": "text",
      "text": "A person walks through a beautiful garden, photorealistic"
    },
    {
      "type": "image_url",
      "role": "reference_image",
      "image_url": {
        "url": "https://example.com/face.jpg"
      }
    }
  ],
  "ratio": "16:9",
  "resolution": "720p",
  "duration": 5,
  "watermark": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| `model` | string | Seedance 2.0 model ID or custom endpoint ID (`ep-xxxx`) |
| `content[].type` | string | `"text"` or `"image_url"` |
| `content[].text` | string | The video generation prompt (text type only) |
| `content[].role` | string | `"reference_image"` — sibling of `type`, not nested inside `image_url` |
| `content[].image_url.url` | string | Public image URL or `asset://{asset_id}` |
| `ratio` | string | Aspect ratio: `"16:9"`, `"9:16"`, `"1:1"`, `"4:3"`, `"3:4"` |
| `resolution` | string | Output resolution: `"720p"` or `"1080p"` |
| `duration` | integer | Video duration in seconds: `5` or `10` |
| `watermark` | boolean | Set to `false` to disable watermark |

> **Multi-image prompts**: Reference images positionally in the prompt text — "Image 1", "Image 2" etc. Do NOT use asset IDs directly in the prompt text.

> **Web app convenience**: The web app accepts `--ratio 16:9 --resolution 1080p --duration 5` appended inline to the prompt text. The backend parses these flags and converts them to the correct top-level API fields before sending to BytePlus.

### Response

```json
{
  "id": "cgt-xxxxxxxxxxxxxxxx",
  "status": "queued",
  "model": "dreamina-seedance-2-0-260128",
  "created_at": 1746786300
}
```

**Extract**: `response["id"]` — this is your `task_id`. Note the `cgt-` prefix format.

---

## Step 4 — Poll for Task Completion

Poll every 5–10 seconds until `status` is `"succeeded"` or `"failed"`.

### Request

```http
GET https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks/cgt-xxxxxxxxxxxxxxxx
Authorization: Bearer <ARK_API_KEY>
```

### Response — Processing

```json
{
  "id": "cgt-xxxxxxxxxxxxxxxx",
  "status": "running",
  "model": "dreamina-seedance-2-0-260128",
  "created_at": 1746786300,
  "updated_at": 1746786360
}
```

### Response — Succeeded

```json
{
  "id": "cgt-xxxxxxxxxxxxxxxx",
  "status": "succeeded",
  "model": "dreamina-seedance-2-0-260128",
  "created_at": 1746786300,
  "updated_at": 1746786600,
  "content": {
    "video_url": "https://cdn-ark.byteplus.com/generated/task-xxxxxxxx/output.mp4"
  }
}
```

**Extract**: `response["content"]["video_url"]` — direct MP4 download link.

### Response — Failed

```json
{
  "id": "cgt-xxxxxxxxxxxxxxxx",
  "status": "failed",
  "error": {
    "code": "InvalidInput",
    "message": "Reference image does not meet portrait requirements."
  }
}
```

| `status` | Meaning |
|----------|---------|
| `queued` | Task is waiting in queue |
| `running` | Video is being generated |
| `succeeded` | Done — use `content.video_url` |
| `failed` | Failed — check `error.message` |

Typical generation time: **2–5 minutes**.

---

## Step 5 — Display the Video

The `content.video_url` is a direct MP4 link. Embed it in a `<video>` element:

```html
<video src="https://cdn-ark.byteplus.com/generated/..." controls autoplay muted loop></video>
```

---

## Complete Python Example

```python
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Video Generation (Bearer token) ─────────────────────────────
VIDEO_BASE   = "https://ark.ap-southeast.bytepluses.com/api/v3"
API_KEY      = os.getenv("ARK_API_KEY")
MODEL_ID     = os.getenv("SEEDANCE_MODEL_ID", "dreamina-seedance-2-0-260128")

# ── Asset Library (HMAC-SHA256 AK/SK) ───────────────────────────
ASSET_HOST    = "ark.ap-southeast-1.byteplusapi.com"
ASSET_BASE    = f"https://{ASSET_HOST}"
ASSET_VERSION = "2024-01-01"
ASSET_REGION  = "ap-southeast-1"
ASSET_SERVICE = "ark"

ARK_AK = os.getenv("ARK_AK")
ARK_SK = os.getenv("ARK_SK")


# ── HMAC-SHA256 signing ──────────────────────────────────────────
def _sign_bytes(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def _asset_headers(action: str, body_str: str) -> dict:
    body_hash = hashlib.sha256(body_str.encode()).hexdigest()
    now       = datetime.now(timezone.utc)
    date_str  = now.strftime("%Y%m%d")
    dt_str    = now.strftime("%Y%m%dT%H%M%SZ")

    canonical = "\n".join([
        "POST", "/", f"Action={action}&Version={ASSET_VERSION}",
        f"content-type:application/json\nhost:{ASSET_HOST}\nx-content-sha256:{body_hash}\nx-date:{dt_str}\n",
        "content-type;host;x-content-sha256;x-date",
        body_hash,
    ])
    scope   = f"{date_str}/{ASSET_REGION}/{ASSET_SERVICE}/request"
    to_sign = "\n".join(["HMAC-SHA256", dt_str, scope,
                          hashlib.sha256(canonical.encode()).hexdigest()])
    k = _sign_bytes(_sign_bytes(_sign_bytes(_sign_bytes(
        ARK_SK.encode(), date_str), ASSET_REGION), ASSET_SERVICE), "request")
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()

    return {
        "Content-Type": "application/json",
        "Host": ASSET_HOST,
        "X-Date": dt_str,
        "X-Content-Sha256": body_hash,
        "Authorization": (
            f"HMAC-SHA256 Credential={ARK_AK}/{scope}, "
            f"SignedHeaders=content-type;host;x-content-sha256;x-date, "
            f"Signature={sig}"
        ),
    }


def call_asset_api(action: str, body: dict) -> dict:
    body_str = json.dumps(body, separators=(",", ":"))
    url      = f"{ASSET_BASE}/?Action={action}&Version={ASSET_VERSION}"
    resp     = requests.post(url, headers=_asset_headers(action, body_str),
                             data=body_str, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── Step 1: Create Asset Group ───────────────────────────────────
def create_asset_group(name: str) -> str:
    data     = call_asset_api("CreateAssetGroup", {
        "Name": name, "Description": "Portrait assets", "GroupType": "AIGC", "ProjectName": "default",
    })
    group_id = data["Result"]["Id"]
    print(f"Asset group created: {group_id}")
    return group_id


# ── Step 2: Create Asset ─────────────────────────────────────────
def create_asset(group_id: str, name: str, image_url: str) -> str:
    data     = call_asset_api("CreateAsset", {
        "GroupId": group_id, "URL": image_url, "AssetType": "Image",
        "Name": name, "ProjectName": "default",
    })
    asset_id = data["Result"]["Id"]
    print(f"Asset created: {asset_id}")
    return asset_id


# ── Step 2b: Poll Asset Status ───────────────────────────────────
def wait_for_asset(asset_id: str, timeout: int = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data   = call_asset_api("GetAsset", {"Id": asset_id, "ProjectName": "default"})
        status = data["Result"].get("Status", "")
        print(f"  Asset status: {status}")
        if status == "Active":
            return True
        if status == "Failed":
            return False
        time.sleep(5)
    raise TimeoutError("Asset verification timed out")


# ── Step 3: Create Video Task ────────────────────────────────────
def create_video_task(prompt: str, asset_id: str,
                      ratio: str = "16:9", resolution: str = "1080p", duration: int = 5) -> str:
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model":      MODEL_ID,
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "role": "reference_image",
             "image_url": {"url": f"asset://{asset_id}"}},
        ],
        "ratio":      ratio,
        "resolution": resolution,
        "duration":   duration,
        "watermark":  False,
    }
    resp    = requests.post(f"{VIDEO_BASE}/contents/generations/tasks",
                            headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    task_id = resp.json()["id"]
    print(f"Video task created: {task_id}")
    return task_id


# ── Step 4: Poll Task Status ─────────────────────────────────────
def wait_for_video(task_id: str, timeout: int = 600) -> str:
    headers  = {"Authorization": f"Bearer {API_KEY}"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp   = requests.get(f"{VIDEO_BASE}/contents/generations/tasks/{task_id}",
                              headers=headers, timeout=15)
        resp.raise_for_status()
        data   = resp.json()
        status = data.get("status", "")
        print(f"  Task status: {status}")
        if status == "succeeded":
            return data["content"]["video_url"]
        if status == "failed":
            raise RuntimeError(f"Task failed: {data.get('error')}")
        time.sleep(10)
    raise TimeoutError("Video generation timed out")


# ── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    face_url = "https://example.com/alice_portrait.jpg"  # Must be publicly accessible
    prompt   = "Alice walks confidently through a sunlit Tokyo street, cinematic tracking shot, photorealistic"

    group_id = create_asset_group("My Portraits")
    asset_id = create_asset(group_id, "Alice", face_url)

    print("Waiting for asset verification…")
    if not wait_for_asset(asset_id):
        raise RuntimeError("Asset verification failed")

    task_id   = create_video_task(prompt, asset_id, ratio="16:9", resolution="1080p", duration=5)
    print("Waiting for video generation…")
    video_url = wait_for_video(task_id)
    print(f"\nVideo ready: {video_url}")
```

---

## Error Codes

| HTTP Status | Meaning | Common Cause | Action |
|-------------|---------|--------------|--------|
| 400 | Invalid request | Wrong body field names, missing required fields | Check PascalCase field names for asset APIs |
| 401 | Auth error | Invalid API key or bad HMAC signature | Verify `ARK_API_KEY`, `ARK_AK`, `ARK_SK`; check signing logic |
| 403 | Permission denied | Asset not yet `Active`, or no access to model | Wait for asset `Active` status; check model access in console |
| 429 | Rate limited | Too many requests | Implement exponential back-off |
| 500 | Server error | BytePlus internal error | Retry with back-off |

---

## References

- [Private Virtual Portrait Library Overview](https://docs.byteplus.com/en/docs/ModelArk/2333565)
- [ListAssetGroups API](https://docs.byteplus.com/en/docs/ModelArk/2318269)
- [CreateAssetGroup API](https://docs.byteplus.com/en/docs/ModelArk/2318270)
- [CreateAsset API](https://docs.byteplus.com/en/docs/ModelArk/2318271)
- [GetAsset API](https://docs.byteplus.com/en/docs/ModelArk/2318273)
- [Seedance 2.0 API Reference](https://docs.byteplus.com/en/docs/ModelArk/1520757)
- [Retrieve Video Generation Task](https://docs.byteplus.com/en/docs/ModelArk/1521309)
