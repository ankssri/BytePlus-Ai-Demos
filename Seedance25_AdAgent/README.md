# Seedance 2.5 Ad Agent

An agentic **idea → brand ad video** app on BytePlus ModelArk. Unlike the v1
keyframe tool (`../Seedance25_AdStudio`), this uses **Seedance 2.5 as intended**:
one long-form (≤30s) generation with **omni-reference consistency** and
**in-place editing/extension** — not stitched clips.

See **`DESIGN.md`** for the full rationale, the platform research it's modelled
on (Higgsfield / InVideo / Freepik / Arcads), and every design decision.

## Pipeline
```
Brief → Script Agent (Seed LLM, structured) → Brand Kit (omni refs) →
Storyboard preview (anchored) → ONE Seedance 2.5 generation → Edit/Extend → Post overlays
```

## Stages in the app
1. **Brief** — describe the ad; pick a sample; set duration/aspect/language; choose
   whether the model may render simple on-screen text (**hybrid** — English/number
   badges only; Hindi/contact/logo always post-overlaid).
2. **Script** — the **Seed LLM** returns a structured **Ad Plan** (scenes, VO Hi+En,
   on-screen badges, a single **director's brief**, and a post-overlay list). Or
   paste your own plan JSON.
3. **Brand Kit** — build the omni-reference set once: upload/generate presenter,
   product, logo, style. Real-person photos are run through Seedream to become
   model-generated (Seedance-trusted) and registered as Assets. Voiceover mode
   **A** (native Hindi) or **B** (exact via reference audio: BytePlus TTS or upload).
4. **Storyboard** — Seedream preview frames (open/hero/CTA); approved frames are
   **anchored** into generation.
5. **Generate** — **one** Seedance 2.5 request: director's brief + Brand Kit +
   approved frames as omni references, `generate_audio`, 9:16, ≤30s.
6. **Edit & Export** — timestamp **edit** / **extend** the generated ad in place
   (no re-stitch); composite the overlay plan (logo, contact bar, ₹ badges,
   captions, music) in your editor.

## Setup
```bash
cd Seedance25_AdAgent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in keys / model ids
python app.py              # http://localhost:8090
```

### Env (`.env` — never committed, never read by the author)
| Variable | Purpose |
|---|---|
| `ARK_API_KEY` | Bearer for Seedream + Seedance + Seed LLM (+ TTS if same) |
| `ARK_AK` / `ARK_SK` | Asset Library HMAC |
| `SEEDREAM_MODEL_ID` | Seedream 5.0 pro |
| `SEEDANCE_MODEL_ID` | Seedance 2.5 |
| `SEED_LLM_MODEL_ID` | Script agent (e.g. `seed-2-0-pro-…`) |
| `TTS_BASE_URL` / `TTS_MODEL_ID` | VO mode B TTS (optional; upload works without) |
| `ASSET_GROUP_ID` | `group-20260401144336-bmrf4` |

## Still needed to run every path
- **`SEED_LLM_MODEL_ID`** — for the Script Agent (paste-plan works without it).
- **BytePlus TTS endpoint** — for VO mode B via TTS (upload-VO works without it).

## API surface (Flask)
| Route | Purpose |
|---|---|
| `POST /api/generate-plan` | Seed LLM → structured Ad Plan |
| `POST /api/seedream`, `POST /api/prepare-face` | Seedream image gen / trusted face pass |
| `POST /api/create-asset`, `GET /api/asset-status/<id>` | Asset Library |
| `POST /api/generate-video`, `GET /api/video-task/<id>` | Seedance 2.5 long-form |
| `POST /api/edit-video`, `POST /api/extend-video` | Seedance edit / extend |
| `POST /api/tts` | VO mode B TTS |
