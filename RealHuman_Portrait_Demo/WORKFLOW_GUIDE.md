# Real-Human Portrait Asset Library — Workflow Guide

Complete API reference for the BytePlus ModelArk **Private Real-Human Portrait Library** and Seedance 2.0 video generation using real-human assets.

---

## Architecture

Two completely different API systems are involved:

| System | Host | Auth | Endpoint pattern |
|--------|------|------|-----------------|
| **Asset Library** | `ark.ap-southeast-1.byteplusapi.com` | HMAC-SHA256 AK/SK | `POST /?Action=<Action>&Version=2024-01-01` |
| **Video Generation** | `ark.ap-southeast.bytepluses.com` | Bearer API Key | `POST /api/v3/contents/generations/tasks` |

---

## Prerequisites

1. **Authorization Letter** — Before calling `CreateAssetGroup` for the first time, sign the authorization letter in the BytePlus Console:
   - Open **Model Playground** → **My assets** → **Real-Human Portrait** → **Manage assets**
   - Sign the letter confirming you have rights to use the real-human portraits
   - This is a **one-time** step per account

2. **Advanced Creation Rights** — Required to access the Real-Human Portrait Library. Capacity quota is shared between the Virtual Portrait Library and the Real-Human Portrait Library.

3. **Credentials**:
   - `ARK_AK` / `ARK_SK` — Access Key for all Asset Library APIs (HMAC-SHA256 signed)
   - `ARK_API_KEY` — Bearer token for Video Generation API only

---

## Step 0 — List Existing Asset Groups

Check whether a real-human portrait group already exists before creating one.

```
POST https://ark.ap-southeast-1.byteplusapi.com/?Action=ListAssetGroups&Version=2024-01-01
Auth: HMAC-SHA256 AK/SK
```

Request body:
```json
{
  "Filter": {
    "GroupType": "LivenessFace"
  },
  "PageNumber": 1,
  "PageSize": 50,
  "SortBy": "CreateTime",
  "SortOrder": "Desc",
  "ProjectName": "default"
}
```

Response:
```json
{
  "ResponseMetadata": { ... },
  "Result": {
    "TotalCount": 2,
    "PageNumber": 1,
    "PageSize": 50,
    "Items": [
      {
        "Id": "group-xxxxxxxx",
        "Name": "My Real-Human Group",
        "GroupType": "LivenessFace",
        "ProjectName": "default",
        "CreateTime": "2026-03-18T03:33:32Z",
        "UpdateTime": "2026-03-18T03:33:32Z"
      }
    ]
  }
}
```

Key difference from virtual portraits: `GroupType` is `"LivenessFace"` (not `"AIGC"`).

---

## Step 1 — Create Asset Group

```
POST https://ark.ap-southeast-1.byteplusapi.com/?Action=CreateAssetGroup&Version=2024-01-01
Auth: HMAC-SHA256 AK/SK
```

Request body:
```json
{
  "Name": "My Real-Human Group",
  "Description": "Real-human portrait assets for Seedance 2.0",
  "GroupType": "LivenessFace",
  "ProjectName": "default"
}
```

Response:
```json
{
  "ResponseMetadata": { ... },
  "Result": {
    "Id": "group-20260318033332-xxxxx"
  }
}
```

Extract the group ID: `(data.get("Result") or {}).get("Id")`

---

## Step 2 — Upload Assets (`CreateAsset`)

Real-human portrait groups support three asset types: **Image**, **Video**, **Audio**.

```
POST https://ark.ap-southeast-1.byteplusapi.com/?Action=CreateAsset&Version=2024-01-01
Auth: HMAC-SHA256 AK/SK
```

Request body:
```json
{
  "GroupId": "group-20260318033332-xxxxx",
  "URL": "https://example.com/portrait.jpg",
  "AssetType": "Image",
  "Name": "Full body shot",
  "ProjectName": "default"
}
```

### Asset type constraints

**Image:**
- Format: jpeg, png, webp, bmp, tiff, gif, heic/heif
- Aspect ratio (w/h): 0.4 – 2.5
- Size: 300 – 6000 px per side; < 30 MB

**Video:** refer to BytePlus Asset API docs for current constraints

**Audio:** refer to BytePlus Asset API docs for current constraints

### Optional: Skip moderation

```json
{
  "GroupId": "...",
  "URL": "...",
  "AssetType": "Image",
  "Moderation": { "Strategy": "Skip" },
  "ProjectName": "default"
}
```

> **Warning:** To enable `Strategy: "Skip"`, you must first **turn off Secure Mode** in the console (`Model Playground` → `My assets` → `Manage assets`). This operation is **irreversible** — once disabled, Secure Mode cannot be re-enabled, and console asset management is permanently disabled. Assets can then only be managed via API.

Response:
```json
{
  "ResponseMetadata": { ... },
  "Result": {
    "Id": "asset-20260318071009-xxxxx"
  }
}
```

---

## Step 2b — Poll Asset Status (`GetAsset`)

`CreateAsset` is asynchronous. Poll until status becomes `Active`.

```
POST https://ark.ap-southeast-1.byteplusapi.com/?Action=GetAsset&Version=2024-01-01
Auth: HMAC-SHA256 AK/SK
```

Request body:
```json
{
  "Id": "asset-20260318071009-xxxxx",
  "ProjectName": "default"
}
```

Response:
```json
{
  "Result": {
    "Id": "asset-20260318071009-xxxxx",
    "Status": "Active",
    "AssetType": "Image",
    "GroupId": "group-20260318033332-xxxxx",
    "URL": "https://ark-media-asset-ap-southeast-1.tos-ap-southeast-1.volces.com/...",
    "ProjectName": "default"
  }
}
```

- **Status values** (always capitalized): `Processing` → `Active` or `Failed`
- The `URL` in the response is **valid for 12 hours only**
- Only `Active` assets can be used for video generation

---

## Step 2c — List Assets in a Group (`ListAssets`)

```
POST https://ark.ap-southeast-1.byteplusapi.com/?Action=ListAssets&Version=2024-01-01
Auth: HMAC-SHA256 AK/SK
```

Request body:
```json
{
  "Filter": {
    "GroupIds": ["group-20260318033332-xxxxx"],
    "GroupType": "LivenessFace",
    "Statuses": ["Active", "Processing"]
  },
  "PageNumber": 1,
  "PageSize": 50,
  "SortBy": "CreateTime",
  "SortOrder": "Desc",
  "ProjectName": "default"
}
```

---

## Step 3 — Generate Video with Real-Human Assets

```
POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks
Auth: Bearer <ARK_API_KEY>
Content-Type: application/json
```

### Single-asset example

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "content": [
    {
      "type": "text",
      "text": "The person in Image 1 walks confidently through a sunlit Tokyo street, cinematic tracking shot"
    },
    {
      "type": "image_url",
      "role": "reference_image",
      "image_url": { "url": "asset://asset-20260318071009-xxxxx" }
    }
  ],
  "ratio": "16:9",
  "resolution": "1080p",
  "duration": 11,
  "watermark": false
}
```

### Multi-asset example (Image + Audio)

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "content": [
    {
      "type": "text",
      "text": "The person in Image 1 presents a product to the camera with a bright smile. Voice style from Audio 1."
    },
    {
      "type": "image_url",
      "role": "reference_image",
      "image_url": { "url": "asset://asset-image-xxxxx" }
    },
    {
      "type": "audio_url",
      "role": "reference_audio",
      "audio_url": { "url": "asset://asset-audio-xxxxx" }
    }
  ],
  "generate_audio": true,
  "ratio": "9:16",
  "resolution": "1080p",
  "duration": 11,
  "watermark": false
}
```

### Key rules for referencing assets in the prompt

- Reference assets by **type + position index**: `Image 1`, `Image 2`, `Video 1`, `Audio 1`
- Index is **per type**: the first image is `Image 1`, the second image is `Image 2`; audio is numbered separately as `Audio 1`
- **Never** reference an Asset ID directly in the prompt text
- Asset URI format: `asset://<asset_id>` used in `content[n].image_url.url` or `content[n].audio_url.url`

### Top-level request fields

| Field | Values | Notes |
|-------|--------|-------|
| `ratio` | `16:9` `9:16` `1:1` `4:3` `3:4` | Output aspect ratio |
| `resolution` | `720p` `1080p` | Output resolution |
| `duration` | `5` `10` `11` | Duration in seconds |
| `generate_audio` | `true` / `false` | AI-generated audio in video |
| `watermark` | `true` / `false` | BytePlus watermark |

### `role` placement

`role` is a **sibling of `type`** in the content item, **not** nested inside `image_url`:

```json
{
  "type": "image_url",
  "role": "reference_image",     ← sibling of type
  "image_url": { "url": "..." }
}
```

---

## Step 4 — Poll Task Status

```
GET https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks/{task_id}
Auth: Bearer <ARK_API_KEY>
```

Task status values: `queued` → `running` → `succeeded` / `failed`

Task ID format: `cgt-...`

---

## Python Example (complete)

```python
import hashlib, hmac, json, os, re, time
from datetime import datetime, timezone
import requests

ASSET_HOST    = "ark.ap-southeast-1.byteplusapi.com"
ASSET_VERSION = "2024-01-01"
ASSET_REGION  = "ap-southeast-1"
ASSET_SERVICE = "ark"
VIDEO_BASE    = "https://ark.ap-southeast.bytepluses.com/api/v3"

ARK_AK  = os.environ["ARK_AK"]
ARK_SK  = os.environ["ARK_SK"]
API_KEY = os.environ["ARK_API_KEY"]


def _sign_bytes(key, msg):
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def asset_headers(action, body_str):
    body_hash = hashlib.sha256(body_str.encode()).hexdigest()
    now       = datetime.now(timezone.utc)
    date_str  = now.strftime("%Y%m%d")
    dt_str    = now.strftime("%Y%m%dT%H%M%SZ")

    canonical = "\n".join([
        "POST", "/", f"Action={action}&Version={ASSET_VERSION}",
        f"content-type:application/json\nhost:{ASSET_HOST}\nx-content-sha256:{body_hash}\nx-date:{dt_str}\n",
        "content-type;host;x-content-sha256;x-date", body_hash,
    ])
    scope = f"{date_str}/{ASSET_REGION}/{ASSET_SERVICE}/request"
    sts   = "\n".join(["HMAC-SHA256", dt_str, scope, hashlib.sha256(canonical.encode()).hexdigest()])

    k = _sign_bytes(_sign_bytes(_sign_bytes(_sign_bytes(ARK_SK.encode(), date_str), ASSET_REGION), ASSET_SERVICE), "request")
    sig = hmac.new(k, sts.encode(), hashlib.sha256).hexdigest()

    return {
        "Content-Type": "application/json",
        "Host": ASSET_HOST,
        "X-Date": dt_str,
        "X-Content-Sha256": body_hash,
        "Authorization": f"HMAC-SHA256 Credential={ARK_AK}/{scope}, SignedHeaders=content-type;host;x-content-sha256;x-date, Signature={sig}",
    }


def call_asset(action, body):
    s   = json.dumps(body, separators=(",", ":"))
    url = f"https://{ASSET_HOST}/?Action={action}&Version={ASSET_VERSION}"
    r   = requests.post(url, headers=asset_headers(action, s), data=s, timeout=30)
    return r.json()


# 1. Create group
group = call_asset("CreateAssetGroup", {
    "Name": "Real-Human Group", "Description": "",
    "GroupType": "LivenessFace", "ProjectName": "default",
})
group_id = (group.get("Result") or {}).get("Id")
print("Group ID:", group_id)

# 2. Upload image asset
asset = call_asset("CreateAsset", {
    "GroupId": group_id,
    "URL": "https://example.com/portrait.jpg",
    "AssetType": "Image",
    "Name": "Portrait",
    "ProjectName": "default",
})
asset_id = (asset.get("Result") or {}).get("Id")
print("Asset ID:", asset_id)

# 3. Poll until Active
for _ in range(60):
    s = call_asset("GetAsset", {"Id": asset_id, "ProjectName": "default"})
    status = (s.get("Result") or {}).get("Status", "")
    print("Status:", status)
    if status == "Active":
        break
    if status == "Failed":
        raise RuntimeError("Asset processing failed")
    time.sleep(5)

# 4. Generate video
resp = requests.post(
    f"{VIDEO_BASE}/contents/generations/tasks",
    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    json={
        "model": "dreamina-seedance-2-0-260128",
        "content": [
            {"type": "text", "text": "The person in Image 1 walks confidently through a sunlit studio"},
            {"type": "image_url", "role": "reference_image", "image_url": {"url": f"asset://{asset_id}"}},
        ],
        "ratio": "16:9", "resolution": "1080p", "duration": 11, "watermark": False,
    },
    timeout=30,
)
task_id = resp.json().get("id")
print("Task ID:", task_id)

# 5. Poll task
for _ in range(72):
    t = requests.get(
        f"{VIDEO_BASE}/contents/generations/tasks/{task_id}",
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=15,
    ).json()
    if t.get("status") == "succeeded":
        print("Video URL:", (t.get("content") or {}).get("video_url"))
        break
    if t.get("status") == "failed":
        raise RuntimeError(t.get("error"))
    time.sleep(10)
```

---

## Known Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| `AccessDenied` on CreateAssetGroup | Authorization letter not signed | Sign in console first |
| `MissingParameter.Filter` on ListAssetGroups | `GroupType` not inside `Filter` object | Nest it: `{"Filter": {"GroupType": "LivenessFace"}}` |
| `MissingParameter` on CreateAsset | Wrong field name casing | All body keys are **PascalCase** |
| Asset stuck in `Processing` | URL not publicly reachable | Ensure the URL is accessible without auth |
| Asset `Active` check never matches | Comparing lowercase `"active"` | API returns capitalized `"Active"` |
| Video `role` field rejected | `role` nested inside `image_url` | `role` must be a sibling of `type` |
| Wrong asset type for audio | Using `image_url` for audio | Use `audio_url` with `role: "reference_audio"` |
| Asset URL expired | CDN links valid for 12 hrs | Download promptly after `GetAsset` |
| `Expecting value: line 1 column 1` | Wrong host for API calls | Asset APIs use a different host from video APIs |
