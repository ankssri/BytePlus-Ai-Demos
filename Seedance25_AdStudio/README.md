# Seedance 2.5 Ad Studio

A step-by-step web app that turns an **ad script** (two markdown files: a
voiceover/shot script + a keyframe-prompt sheet) into a finished vertical ad
video, using **Seedream 5.0 pro** for keyframes and **Seedance 2.5** for video.

It reproduces the recreation pipeline for the *Galaxy Honda / Honda Elevate*
style promo, but works for any script in the same markdown format.

```
Load script → Generate keyframes → (edit) → Upload to Asset Library → Generate video → Assemble
   (parse)      Seedream 5.0 pro                Asset Library API         Seedance 2.5      ffmpeg
```

## Why the Asset Library step?

Seedance 2.5 reads reference images/videos/audio from the BytePlus **Asset
Library** (and does not accept raw human-face uploads directly). So every
approved keyframe is first registered as an `Image` asset; the returned
`asset://<id>` is then used as the video's first frame. This mirrors the
[`Seedance2_Portrait_Demo`](../Seedance2_Portrait_Demo) asset flow, applied to
Seedance 2.5.

## Workflow (what each step does)

1. **Load script** — Read a bundled sample, upload, or paste the two markdown
   files. The parser extracts the voiceover table + shot table + per-keyframe
   image/motion prompts and **matches each keyframe to the dialogue spoken in
   its time window**.
2. **Generate keyframes (Seedream 5.0 pro)** — One start-frame image per shot.
   **Regenerate** (new seed) or **Edit** (feed the frame back with an
   instruction) until correct, then **Approve**.
3. **Upload to Asset Library** — Register each approved keyframe URL as an
   `Image` asset in your asset group, poll until ready → `asset://<id>`.
4. **Generate video (Seedance 2.5)** — First-frame image-to-video per shot. The
   matched dialogue is placed in double quotes with `generate_audio=true`, so
   the presenter speaks/lip-syncs the Hindi line.
5. **Assemble** — Collect the per-shot clips in order; stitch with server-side
   `ffmpeg` if available, or copy the printed concat command.

## Setup

```bash
cd Seedance25_AdStudio
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill in your keys / model ids
python app.py             # http://localhost:8080
```

### Environment (`.env` — never committed, never read by the app author)

| Variable | Purpose |
|---|---|
| `ARK_API_KEY` | Bearer key for Seedream (image) + Seedance (video) |
| `ARK_AK` / `ARK_SK` | HMAC AK/SK for the Asset Library API |
| `SEEDREAM_MODEL_ID` | Seedream 5.0 pro model / endpoint id |
| `SEEDANCE_MODEL_ID` | Seedance 2.5 model / endpoint id |
| `ASSET_GROUP_ID` | Asset group for uploads (default `group-20260401144336-bmrf4`) |
| `PORT`, `FLASK_DEBUG` | Server settings |

The app reads secrets **only** from the environment. Endpoint hosts default to
`ap-southeast` and can be overridden in `.env`.

## Script markdown format

Two files per script (see `sample_scripts/`):

- **`*_offer_led.md` / script file** — a **Voiceover** table
  (`# | Time | Hindi | Romanized | English`) and a **Shot-by-shot** table
  (`KF | ~Time | camera | action | setting | graphic`).
- **`*_keyframes.md` / keyframes file** — a `**PRESENTER (…):**` block, then one
  `## <KF> — <title> (<time>)` section per keyframe, each with an
  `**Image prompt:**` blockquote and a `**Seedance 2.5 motion:**` blockquote.
  The token `[PRESENTER]` in image prompts is substituted with the presenter block.

Shots with no image prompt (e.g. the outro contact card) are flagged as
**graphic / post** and skipped for Seedream generation.

Bundled samples: `script_A` (offer-led) and `script_B` (lifestyle/family-led),
each with a new Indian presenter (Hindi + English VO).

## Prompt best practices (Seedance 2.5)

Baked into the prompt composer, from the BytePlus API docs / Seedance 2.5 prompt
guide (full guide PDF:
`/Users/bytedance/Documents/PromptsBestPractices/Mdfiles/Seedance-2.5-prompt-guide.pdf`):

- Put **spoken dialogue in double quotes** for clean audio (`generate_audio`).
- Keep prompts under ~1,000 English words; lead with the shot/motion.
- First-frame image-to-video on 2.5 uses `ratio: adaptive` (it preserves the
  first frame's aspect); set `resolution` (`720p`/`1080p`) instead.
- Seedance 2.5 supports Hindi/English and 9 other languages in prompts.

## API surface (Flask)

| Route | Purpose |
|---|---|
| `GET /api/config` | non-secret config/status booleans |
| `GET /api/samples`, `GET /api/sample` | bundled sample scripts |
| `POST /api/parse-script` | markdown → structured shots + matched dialogue |
| `POST /api/generate-keyframe` | Seedream text-to-image |
| `POST /api/edit-keyframe` | Seedream image edit |
| `POST /api/create-asset`, `GET /api/asset-status/<id>` | Asset Library |
| `POST /api/create-video-task`, `GET /api/video-task/<id>` | Seedance 2.5 |
| `POST /api/stitch` | optional local ffmpeg concat |

See `WORKFLOW_GUIDE.md` for a hands-on run-through.
