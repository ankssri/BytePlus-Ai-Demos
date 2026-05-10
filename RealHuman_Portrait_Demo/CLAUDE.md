# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
cd RealHuman_Portrait_Demo
cp .env.example .env          # fill in ARK_API_KEY, ARK_AK, ARK_SK
pip install -r requirements.txt
python app.py                 # http://localhost:5051
```

No build step, no test suite.

---

## Critical Architecture: Two Separate API Systems

| System | Host | Auth | Endpoint pattern |
|--------|------|------|-----------------|
| **Asset Library** | `ark.ap-southeast-1.byteplusapi.com` | HMAC-SHA256 AK/SK | `POST /?Action=<Action>&Version=2024-01-01` |
| **Video Generation** | `ark.ap-southeast.bytepluses.com` | Bearer API Key | `POST /api/v3/contents/generations/tasks` |

These are **not** the same host with different paths.

### Credentials

```
ARK_API_KEY   → Bearer token for video APIs only
ARK_AK        → Access Key ID for asset APIs (HMAC-SHA256)
ARK_SK        → Secret Access Key for asset APIs (HMAC-SHA256)
```

### HMAC-SHA256 Signing

All three of `_sign_bytes`, `_asset_signed_headers`, and `_call_asset_api` must be used together. The signing chain:

```
canonical_request = "POST" + "\n" + "/" + "\n" + "Action=X&Version=2024-01-01" + "\n"
                  + canonical_headers + "\n" + signed_headers_list + "\n" + body_sha256
string_to_sign    = "HMAC-SHA256" + "\n" + datetime + "\n" + scope + "\n" + sha256(canonical_request)
signing_key       = HMAC(HMAC(HMAC(HMAC(SK, date), region), service), "request")
signature         = HMAC(signing_key, string_to_sign).hexdigest()
```

Body **must** be serialised with `json.dumps(body, separators=(",", ":"))` — no spaces — before hashing.

---

## Key Difference from Seedance2_Portrait_Demo

This demo uses `GroupType: "LivenessFace"` for real-human portrait groups.  
The virtual portrait demo uses `GroupType: "AIGC"`.  
Both demos share the same API host and HMAC-SHA256 signing.

**Additional prerequisite:** The authorization letter must be signed in the BytePlus Console before the first `CreateAssetGroup` call.

---

## Asset API Field Names (PascalCase — not camelCase)

| Action | Key request body keys | Response extraction |
|--------|----------------------|---------------------|
| `ListAssetGroups` | `Filter: {GroupType: "LivenessFace"}` (required), `PageNumber`, `PageSize` | `Result.TotalCount`, `Result.Items[].Id/Name` |
| `CreateAssetGroup` | `Name`, `Description`, `GroupType: "LivenessFace"`, `ProjectName: "default"` | `Result.Id` |
| `CreateAsset` | `GroupId`, `URL`, `AssetType` (`Image`/`Video`/`Audio`), `Name`, `ProjectName` | `Result.Id` |
| `GetAsset` | `Id`, `ProjectName` | `Result.Status`, `Result.URL` (valid 12 hrs) |
| `ListAssets` | `Filter: {GroupIds: [...], GroupType: "LivenessFace"}`, `PageNumber`, `PageSize` | `Result.Items[].Id/Status/AssetType` |

**Asset status values are capitalised**: `Active`, `Processing`, `Failed`.

All asset responses: `{ ResponseMetadata: {...}, Result: {...} }`. Extract via `(data.get("Result") or {}).get("Id")`.

---

## Multi-Asset Video Generation

The video generation API accepts multiple assets in the `content` array:

```json
{
  "model": "dreamina-seedance-2-0-260128",
  "content": [
    { "type": "text", "text": "The person in Image 1 wearing Image 2's outfit..." },
    { "type": "image_url", "role": "reference_image", "image_url": { "url": "asset://asset-xxx" } },
    { "type": "image_url", "role": "reference_image", "image_url": { "url": "asset://asset-yyy" } },
    { "type": "audio_url", "role": "reference_audio", "audio_url": { "url": "asset://asset-zzz" } }
  ],
  "generate_audio": true,
  "ratio": "16:9",
  "resolution": "1080p",
  "duration": 11,
  "watermark": false
}
```

**Prompt referencing rules:**
- Use `Image 1`, `Image 2`, `Video 1`, `Audio 1` — **type + position index**
- Index is per type (images and audio numbered independently)
- **Never** use an Asset ID directly in prompt text

**`role` field placement:** `role` is a **sibling of `type`** in the content item, not nested inside `image_url`/`audio_url`.

### Top-level fields (not in prompt text)

| Field | Type | Notes |
|-------|------|-------|
| `ratio` | string | `16:9`, `9:16`, `1:1`, `4:3`, `3:4` |
| `resolution` | string | `720p`, `1080p` |
| `duration` | int | `5`, `10`, `11` |
| `generate_audio` | bool | AI-generated audio |
| `watermark` | bool | BytePlus watermark |

`_parse_prompt_flags()` in `app.py` extracts `--ratio`, `--duration`, `--resolution` from prompt text into these top-level fields.

---

## Frontend State

`state` in `app.js`:
- `groupId` — the active `LivenessFace` group
- `registeredAssets` — `[{asset_id, asset_type, name, status, ref_label}]`
- `taskId`, `pollTimer`, `assetPollTimer`

`getRefLabel(asset)` computes the positional label (`Image 1`, `Audio 1` etc.) by counting same-type assets that precede the entry in `registeredAssets`.

The asset reference guide panel updates dynamically as assets become `Active` and shows which prompt labels map to which assets.

---

## Inspector Tabs

Each panel has a `<details class="inspector">` with tab buttons (`.itab`) and `<pre class="code-block">` panels. The active tab logic in `app.js` uses `container.querySelector(`#${tab.dataset.tab}`)`.

Asset inspector tabs: `req-list-groups`, `req-create-group`, `req-asset`, `req-list-assets`, `res-*` counterparts.

Video inspector tabs: `req-video`, `res-video-create`, `res-video-poll`.

---

## Known Bugs Fixed (do not reintroduce)

| Bug | Root cause | Fix |
|-----|-----------|-----|
| `Expecting value: line 1 column 1` | `resp.json()` on empty body when wrong host used | `_safe_json()` wraps all JSON parsing |
| `MissingParameter.Filter` on ListAssetGroups | `GroupType` top-level; must be inside `Filter: {}` | Nested correctly; `PageNum` → `PageNumber`; `Total` → `TotalCount` |
| `AccessDenied` on video task | `--ratio`/`--duration`/`--resolution` left in prompt | `_parse_prompt_flags()` extracts to top-level fields |
| Asset `Active` check never triggered | JS compared lowercase `"active"` | API returns `"Active"`; comparisons use capitalized value |
| Wrong asset host | Used video host for asset APIs | Asset host is `ark.ap-southeast-1.byteplusapi.com` |
| `role` field rejected | `role` nested inside `image_url` | `role` must be sibling of `type` at content-item level |

---

## Adding a New Asset API Action

1. Add a Flask route calling `_call_asset_api("ActionName", body)` with PascalCase body keys.
2. Extract via `(data.get("Result") or {}).get("FieldName")`.
3. Add frontend fetch calling the new route.
4. Add inspector tab button + `<pre>` + `setInspector()` call.
