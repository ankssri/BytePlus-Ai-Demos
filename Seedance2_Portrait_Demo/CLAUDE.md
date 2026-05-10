# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
cd Seedance2_Portrait_Demo
cp .env.example .env          # fill in ARK_API_KEY, ARK_AK, ARK_SK
pip install -r requirements.txt
python app.py                 # http://localhost:5050
```

No build step, no test suite. The app runs as a single Flask process; reload is automatic in debug mode.

---

## Critical Architecture: Two Separate API Systems

This is the single most important thing to understand. BytePlus ModelArk uses **two completely different hosts and authentication schemes** for the asset library versus video generation:

| System | Host | Auth | Endpoint pattern |
|--------|------|------|-----------------|
| **Asset Library** | `ark.ap-southeast-1.byteplusapi.com` | HMAC-SHA256 AK/SK | `POST /?Action=<Action>&Version=2024-01-01` |
| **Video Generation** | `ark.ap-southeast.bytepluses.com` | Bearer API Key | `REST /api/v3/contents/generations/tasks` |

These are **not** the same host with different paths. Sending an asset request to the video host (or vice versa) returns an empty body or auth error.

### Credentials

```
ARK_API_KEY   → Bearer token for video APIs only
ARK_AK        → Access Key ID for asset APIs (HMAC-SHA256)
ARK_SK        → Secret Access Key for asset APIs (HMAC-SHA256)
```

### HMAC-SHA256 Signing (`_asset_signed_headers` in app.py)

All three of `_sign_bytes`, `_asset_signed_headers`, and `_call_asset_api` must be used together. The signing chain is:

```
canonical_request = METHOD + "\n" + "/" + "\n" + "Action=X&Version=2024-01-01" + "\n"
                  + canonical_headers + "\n" + signed_headers_list + "\n" + body_sha256
string_to_sign    = "HMAC-SHA256" + "\n" + datetime + "\n" + scope + "\n" + sha256(canonical_request)
signing_key       = HMAC(HMAC(HMAC(HMAC(SK, date), region), service), "request")
signature         = HMAC(signing_key, string_to_sign).hexdigest()
```

Required headers: `Content-Type`, `Host`, `X-Date` (format `YYYYMMDDTHHmmSSZ`), `X-Content-Sha256` (SHA-256 of raw body bytes).

The body **must** be serialised with `json.dumps(body, separators=(",", ":"))` — no spaces — before hashing and sending.

---

## Asset API Field Names (PascalCase — not camelCase)

All asset API request bodies use PascalCase. Using the wrong case returns `MissingParameter` errors.

| Action | Request body keys | Response extraction |
|--------|-------------------|---------------------|
| `ListAssetGroups` | `Filter: {GroupType: "AIGC"}` (required), `PageNumber`, `PageSize`, `SortBy`, `SortOrder`, `ProjectName` | `Result.TotalCount`, `Result.Items[].Id/Name` |
| `CreateAssetGroup` | `Name`, `Description`, `GroupType: "AIGC"`, `ProjectName: "default"` | `Result.Id` |
| `CreateAsset` | `GroupId`, `URL` (public HTTPS only — no base64), `AssetType: "Image"`, `Name`, `ProjectName` | `Result.Id` |
| `GetAsset` | `Id`, `ProjectName` | `Result.Status` (`Processing` / `Active` / `Failed`) |

**Asset status values are capitalised**: `Active`, `Processing`, `Failed` — not lowercase.

All asset responses wrap their data: `{ ResponseMetadata: {...}, Result: {...} }`. Always extract via `(data.get("Result") or {}).get("Id")`.

---

## Video Generation API

### Request shape

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "content": [
    { "type": "text", "text": "prompt text here" },
    { "type": "image_url", "role": "reference_image", "image_url": { "url": "asset://asset-xxx" } }
  ],
  "ratio": "16:9",
  "resolution": "1080p",
  "duration": 5,
  "watermark": false
}
```

Key constraints:
- `role` is a **sibling** of `type` in the content item, not nested inside `image_url`.
- `ratio`, `resolution`, `duration` are **top-level fields**, not inline in the prompt text.
- Asset reference uses the URI scheme `asset://{asset_id}`.
- Task IDs returned by BytePlus have the format `cgt-...`.

### Inline flag parsing

The web app accepts `--ratio 16:9 --resolution 1080p --duration 5` appended to the prompt for UX convenience. `_parse_prompt_flags()` in `app.py` extracts these with regex and moves them to top-level payload fields before the request is sent. The clean prompt (flags removed) goes into `content[0].text`.

### Polling

`/api/video-task/<task_id>` polls `GET /api/v3/contents/generations/tasks/{id}`. The video URL is normalised from several possible response shapes and exposed as `data["_video_url"]`. Task statuses: `queued` → `running` → `succeeded` / `failed`.

---

## Frontend–Backend Data Flow

The frontend (`static/js/app.js`) sends simplified JSON to the Flask proxy (`app.py`), which translates it into the correct BytePlus format:

```
Frontend → Flask                Flask → BytePlus
──────────────────              ────────────────────────────────────
{prompt, model_id, asset_id} → {model, content:[...], ratio, ...}
{group_id, name, url}        → {GroupId, URL, AssetType, Name, ...}
{name, description}          → {Name, Description, GroupType, ...}
```

The `create_video_task` route appends `_byteplus_request` to its response so the frontend inspector can display the actual payload sent to BytePlus (not the simplified frontend body).

### Asset group reuse flow

When the user clicks "Load Existing Groups", `GET /api/list-asset-groups` is called. Selecting a group from the dropdown sets `state.groupId` in JS. If `state.groupId` is already set when "Register Portrait Asset" is clicked, the `CreateAssetGroup` API call is skipped entirely and `CreateAsset` is called directly into the existing group.

---

## Inspector Tabs

Each panel has a `<details class="inspector">` with tab buttons (`.itab`) and `<pre class="code-block">` panels. The active tab logic in `app.js` uses `container.querySelector(`#${tab.dataset.tab}`)`. Adding a new inspector tab requires: a button with `data-tab="my-id"`, a `<pre id="my-id">`, and a `setInspector("my-id", obj)` call in JS.

---

## Known Bugs Fixed (do not reintroduce)

| Bug | Root cause | Fix |
|-----|-----------|-----|
| `Expecting value: line 1 column 1` crash | `resp.json()` called on empty body when wrong host was used | `_safe_json()` helper wraps all JSON parsing |
| `MissingParameter.Filter` on ListAssetGroups | `GroupType` was top-level; must be inside `Filter: {}` | Nested correctly; `PageNum` → `PageNumber`; `Total` → `TotalCount` |
| `AccessDenied` on video task | `--ratio`/`--duration`/`--resolution` left as literal text in prompt | `_parse_prompt_flags()` extracts them to top-level fields |
| Asset `Active` check never triggered | JS compared against lowercase `"active"` | API returns `"Active"` (capitalised); comparisons updated |
| Wrong asset host | Used video host for asset APIs | Asset host is `ark.ap-southeast-1.byteplusapi.com` |
| `CreateAsset` rejected image | Sent base64 data URI | API only accepts public HTTPS URLs; UI changed to URL input |
| Response parsing returned `None` | Used `data.get("id")` | Must use `(data.get("Result") or {}).get("Id")` |

---

## Adding a New Asset API Action

1. Add a Flask route that calls `_call_asset_api("ActionName", body)` with PascalCase body keys.
2. Extract results via `(data.get("Result") or {}).get("FieldName")`.
3. Add a frontend fetch call that POSTs/GETs the new Flask route.
4. Add inspector tab entries in `index.html` and a `setInspector()` call in `app.js`.

All signing is handled automatically by `_call_asset_api` → `_asset_signed_headers`.
