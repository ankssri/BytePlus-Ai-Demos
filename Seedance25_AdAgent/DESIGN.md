# Seedance 2.5 Ad Agent — Design

An agentic **idea → brand ad video** workflow built on BytePlus ModelArk, using
Seedance 2.5 the way it's meant to be used: **one long-form (≤30s) generation
with omni-reference consistency + in-place editing**, not many stitched clips.

## Why this exists (what the v1 keyframe app got wrong)

v1 (`../Seedance25_AdStudio`) generated 9 keyframes → 9 separate ~3s
image-to-video clips → ffmpeg stitch. That throws away Seedance 2.5's core
strengths. v2 uses them:

| Seedance 2.5 capability | How the Ad Agent uses it |
|---|---|
| Long-form ≤30s single request | The whole ad is **one generation** (cuts/pacing handled by the model) |
| Omni reference (many image/video/audio assets) | The **Brand Kit** = presenter + product + logo + style + optional VO, passed once, locks identity across the whole ad |
| Multi-round extension | Ads longer than 30s are **extended**, not stitched |
| Timestamp-based editing | Fix "the 12–15s benefit card" **in place** (feed the generated ad back as `reference_video`) |
| Native audio (generate_audio) | Voiceover, SFX, music — dialogue in double quotes |

Benchmarks this mirrors: Higgsfield (Brand Kit + Soul ID → one-pass generate),
InVideo (script → scenes → generate → text edits), Freepik (persistent
Characters/Brands/Products → storyboard → generate), Arcads/Creatify (actor +
script → talking ad + batch variants).

## Pipeline

```
0 BRIEF        brand · product · offers · CTA+contact · tone · language(Hi+En) ·
               duration(≤30s) · aspect(9:16) · presenter type
               input: (a) paste brief/script, OR (b) LLM Script Agent
1 SCRIPT       Seed LLM (Chat API + json_schema) → Ad Plan (structured):
  AGENT        scenes[ t_start,t_end, vo_hi, vo_en, on_screen_text, camera, action ],
  (optional)   + director_brief (the single ≤30s Seedance prompt), + overlay_text[]
2 BRAND KIT    build omni-reference set ONCE → Asset Library:
  (once)       presenter identity, product, logo, showroom, style frames,
               + optional reference VO/voice  → asset://ids reused everywhere
3 STORYBOARD   Seedream 5.0 pro → approval frames (open / hero / CTA)  [GATE]
  (preview)    → APPROVED frames are ANCHORED into generation (decision Q2)
4 GENERATE     Seedance 2.5, ONE request ≤30s:
  (Seedance)   content = director_brief + omni-refs (brand kit + approved frames as
               first_frame/reference_image) ; generate_audio ; ratio/resolution.
               VO mode A (native Hindi) or B (reference audio). >30s → extend.
5 EDIT         Seedance 2.5 timestamp edit / extend, feeding the generated ad back
               as reference_video. No re-stitch.
6 BRAND POST   overlays: logo, contact bar, benefit badges, captions + music.
7 VARIANTS     hook/style variants reuse the same Brand Kit; export.
  + EXPORT
```

## Decisions (locked with the user)

1. **On-screen text — Hybrid.** A per-project toggle "model-rendered text?".
   - OFF (default): all text is **post overlay** (logo, ₹ badges, contact, captions).
   - ON: Seedance renders only **short English/number badges** (e.g. "₹2.45 Lakh",
     "7-Yr Warranty"); **Hindi, phone, address, logo are always post overlays**
     (Devanagari + long text garble in-model). The workflow branch adjusts the
     director-brief (adds/omits on-screen-text cues) and the overlay list accordingly.
2. **Storyboard frames are ANCHORED** into the Seedance generation (approved
   opening frame → `first_frame`; hero/product frames → `reference_image`), so the
   video matches what the user approved.
3. **VO does BOTH:** mode A native Hindi speech (dialogue in quotes); mode B exact
   script + lip-sync via **reference audio** — audio comes from **BytePlus TTS
   (endpoint provided) OR user upload**, registered as an Asset and passed to Seedance.
4. **Duration ≤30s single generation**; extend only if longer.
5. **Storyboard preview gate kept.**
6. **New app folder** (`Seedance25_AdAgent`); `Seedance25_AdStudio` kept as-is.
7. **Script step offers both** paste and LLM agent.

## Model / service mapping

| Concern | Service |
|---|---|
| Brief → Ad Plan (structured) | **Seed LLM** Chat API `/chat/completions`, `response_format: json_schema` (strict) |
| Brand-kit / identity / product / storyboard images | **Seedream 5.0 pro** `/images/generations` (+ image edit) |
| The ad video (long-form, omni-ref, edit, extend) | **Seedance 2.5** `/contents/generations/tasks` |
| Reference-audio VO (mode B) | **BytePlus TTS** endpoint (TBD) or user upload |
| Consistent, exact on-screen brand text, captions, music | **Post overlay** (ffmpeg/PIL), always for Hindi/contact/logo |

## Asset / URL handling (important integration note)

- Seedance omni-ref `image_url.url` / `audio_url.url` accept a **public URL, a
  base64 data URI, or `asset://<id>`**. But Seedance 2.5 **rejects raw uploads
  containing real human faces** — those must be **model-generated or Asset-Library
  trusted**.
- Therefore:
  - **Presenter identity:** either Seedream-generate it (returns a public URL) OR,
    if the user uploads a real photo, run it through a Seedream identity-preserving
    pass to produce a **trusted, model-generated** public URL. Then `CreateAsset`
    → `asset://id`.
  - **Product / logo / style (non-face):** pass base64/URL directly to Seedance, or
    register as assets for reuse.
  - **Audio (VO):** register as an `Audio` asset (needs a URL) — TTS output URL, or
    upload path that yields a URL.
- `CreateAsset` needs a URL (not base64); the client encapsulates "get a URL for
  this local file" (Seedream pass for faces; TOS/served URL otherwise).

## App structure

```
Seedance25_AdAgent/
├── app.py                 Flask orchestration (stage routes)
├── schemas.py             json_schema for the Ad Plan (structured output)
├── overlays.py            post overlay compositor (logo/contact/badges/captions)
├── byteplus/
│   ├── config.py          env accessors + non-secret status
│   ├── seedream.py        image gen / edit
│   ├── assets.py          Asset Library (HMAC): create/get/list
│   ├── seedance.py        video: create/query, omni-ref content builder, edit/extend
│   ├── llm.py             Seed Chat API + structured output → Ad Plan
│   └── tts.py             TTS (configurable) + upload path
├── sample_briefs/         example briefs (incl. Galaxy Honda)
├── templates/index.html
└── static/{css,js}
```

## Env (all secrets in .env; never read by the author)

```
ARK_API_KEY            bearer for Seedream + Seedance + Seed LLM (+ TTS if same)
ARK_AK / ARK_SK        Asset Library HMAC
SEEDREAM_MODEL_ID      image gen/edit
SEEDANCE_MODEL_ID      video
SEED_LLM_MODEL_ID      script agent (e.g. seed-2-0-pro-…)   [user provides]
TTS_MODEL_ID / TTS_*   VO mode B TTS                        [user provides / TBD]
ASSET_GROUP_ID         group-20260401144336-bmrf4
PORT / FLASK_DEBUG
```

## Open items still needed from the user
- **Seed LLM model id / endpoint** for the script agent (Chat API base URL assumed
  `…/api/v3/chat/completions`).
- **BytePlus TTS API** (endpoint + request shape) for VO mode B TTS source; until
  provided, mode B works via **user-uploaded VO** and TTS is a configurable stub.

## Competitive benchmark → feature roadmap

Benchmarked against Higgsfield, InVideo, Runway, Freepik, Kling, Hailuo, Pika,
Arcads, Creatify, AdCreative, Google Flow/Veo, Adobe Firefly. The consolidated
best-practice pipeline is: **Brief/format → Asset ("Ingredient") registration →
Script + hook variants → Storyboard approval gate → generation → in-place edit →
audio → export/A-B**. Feature status against that superset:

| Feature (source pattern) | Tier | Status |
|---|---|---|
| Format-first platform presets (InVideo) | table-stakes | **Built** — TikTok/Reels/Shorts/YouTube/Square set aspect+duration |
| Typed references: presenter/product/logo/style (Runway labeled refs, Flow Ingredients) | table-stakes | **Built** — roles bound as `@Image N` |
| Agent proposes + one-click generates the reference set from the plan (Flow Ingredients, Higgsfield) | differentiator | **Built** — Brand Kit derives presenter/product prompts from the plan |
| Per-frame "which references apply" toggle (Kling) | differentiator | **Built** — storyboard reference chips |
| Multi-image same-subject binding, front/¾/side (Kling Elements, Hailuo) | table-stakes | **Built** — same-role refs bound as one subject "from multiple references" |
| Auto hook/angle variations, user-picks the opener (Creatify, Arcads) | differentiator | **Built** — hook picker sets the opening VO |
| Cheap keyframe storyboard **before** spending video credits (Seedream stills) | differentiator | **Built** — Storyboard approval gate |
| Native audio + lip-sync in one pass (Seedance) | table-stakes | **Built** — `generate_audio` |
| In-place single-shot / timestamp edit + extend (Runway Aleph, Seedance edit) | table-stakes | **Built** — Edit/Extend |
| Chat-to-edit the whole ad (InVideo Magic Box) | table-stakes | **Built (basic)** — edit-instruction box |
| Trained identity tier (Higgsfield Soul ID, Firefly custom models) | differentiator | Deferred — needs model-training infra we don't have; multi-image binding is our substitute |
| Per-shot model routing (InVideo, Freepik) | differentiator | N/A — single video model (Seedance 2.5) |
| Batch variation matrix / CSV A-B (Arcads, Creatify Batch) | differentiator | Roadmap — reuse Brand Kit, generate N hook variants |
| One-click aspect-ratio variants from one master (most) | table-stakes | Roadmap |
| Auto-captions/subtitles burn-in + music bed (InVideo) | table-stakes | Partial — overlay plan lists them; needs ffmpeg/PIL compositor (`overlays.py`) |
| Performance scoring / direct publish to ad platforms (AdCreative, Creatify) | differentiator | Out of scope |
| Product-URL ingestion → auto brief (Higgsfield, Creatify) | table-stakes | Roadmap — scrape page → prefill brief |

**Consistency stack we settled on** (the biggest pain point): project-level typed
reference registration (Flow) + labeled multi-image `@Image N` bindings (Runway) +
same-subject multi-angle grouping (Kling) + a Seedream keyframe approval gate that
locks the look cheaply *before* video spend, then Seedance in-place edit for
product/packaging swaps (Aleph pattern). Trained identity (Soul ID) is the one tier
we can't yet match and is the main future upgrade.
