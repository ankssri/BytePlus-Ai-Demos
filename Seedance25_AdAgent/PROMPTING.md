# Prompting reference (Seedream 5.0 + Seedance 2.5, advertising)

Distilled from the BytePlus guides in `prompt_guides/` (Seedream prompt
structure, Seedance 2.5 prompt guide, and the Seedance Advertising playbook) and
the Seedance 2.5 prompt-optimizer skill `sd25-pe`. These rules are encoded into
the Script Agent system prompt (`byteplus/llm.py`), the Seedream composer
(`byteplus/seedream.py`), and the asset-binding step (`app.py`). Read this before
changing any prompt logic.

## A. Seedream 5.0 pro — image prompt structure (6 parts)

`(Picture Quality) + (Subject & Features) + (Environment & Background) +
(Composition & Shot) + (Style & Atmosphere) + (Lighting & Color)`

- Describe **content** (subject, action, environment) in coherent natural
  language; describe **aesthetics** (style, lighting, composition) with precise
  short phrases/terms.
- Params: `size` accepts `1K`/`2K`/`4K` or `WxH` — use **2K** for storyboard
  frames; `ratio` can be stated in natural language ("vertical 9:16 mobile
  wallpaper"); `output_format` png for lossless/transparency; **fix `seed`** for
  consistency; `optimize_prompt=true` (default) rewrites colloquial prompts —
  keep on unless you need exact control; `sequential_image_generation=auto`
  generates a **consistent set** of frames in one call (great for storyboards).
- Prefer positive phrasing; use negative prompt only for stubborn artifacts
  (text, watermark, extra limbs).

## B. Seedance 2.5 — video prompt structure

Write like a visual content producer. A strong prompt has:

1. **One-sentence summary** — Subject + Location + Event + Genre/Style + Camera.
2. **Asset bindings** — number every reference by **upload order** (`@Image 1`,
   `@Video 1`, `@Audio 1`) and bind each in text ("the presenter in @Image 1",
   "@Audio 1 is the voiceover"). NEVER rely on labels drawn inside an image.
3. **Detailed plot** — a timeline with **integer-second timestamps** (1s unit),
   **continuous, no gaps** (`0-3s … 3-7s …`), ~2-3s per beat. Each beat:
   visuals, camera movement, action, **dialogue in double quotes**, sound.
4. **Additional notes** — elements consistent throughout (camera, environment,
   atmosphere, style).
5. **Negatives** — only for subtitles/audio: `"no subtitles"`, `"no BGM"`.

Camera language may be written directly (wide/medium/close-up; push in/pull out/
pan/track/orbit/handheld; low angle/overhead/FPV; dolly zoom, speed ramp).
Timestamps must be continuous; don't micro-control high-frequency actions.

**Task-type rules (locked vs unlocked):**
- **Reference-to-video** (our default): `omni_reference_task_type=reference`,
  ratio + duration user-set (9:16, ≤30s). Anchor frames via `reference_image`
  and say "Image 1 is the first frame" in the prompt (does not hard-lock ratio).
- **First/last frame**: role `first_frame`/`last_frame` — locks ratio to the
  first frame; mutually exclusive with omni references.
- **Editing**: prompt must contain an edit trigger (edit/add/remove/replace/
  change); `ratio=adaptive`, `duration=-1`, `output_format=mov`.
- **Extension**: prompt must contain continue/extend; `ratio=adaptive`, `mov`.

Limits: ≤30 images, ≤10 videos (≤30s total), ≤10 audio (≤30s total); 1-8 image
subjects work well; storyboards ≤15 line-art panels.

## C. Advertising prompt framework (from the ad playbook)

**Required:** Subject (person/product) · Selling-point demonstration (turn the
claim into a concrete micro-action / pain-point scene) · Commercial intent.
**Optional:** Consumption scenario & tone · Camera language (the visual hook) ·
Audio (SFX + beat cues) · Post-production constraints (reserve space for
overlays; negatives like "no subtitles, no watermark").

**Native structure:** **Hook + Product + CTA.** First ~3s = visual or auditory
hook; middle = clear product demo (multi-angle / before-after / real use);
end = explicit CTA (offer, urgency, link). Cut every **2-3s**.

**@-reference syntax:** @Image locks static features (product appearance/logo,
model face/clothing, scene tone, first/last frame); @Video replicates dynamics
(action rhythm, camera moves — say "only reference the camera/expression, not
the character"); @Audio drives lip-sync / beat alignment.

**Tag each line with its role** (as in the examples below), e.g. `[Subject]`,
`[Selling Point Demonstration]`, `[Consumption Scenario and Tone]`,
`[Visual Hook and Camera Movement]`, `[Audio-Visual Synchronization]`,
`[Post-Production Constraints]`.

### Canonical example — Brand (10s men's serum)
> Display the men's serum glass bottle from @Image 1 at the center of the frame,
> transparent premium glass texture, proportions preserved. **[Subject]**
> Refer to the minimalist modern space and cool blue tone in @Image 2; light
> from the side creates a strong contour highlight. **[Consumption Scenario and Tone]**
> Water droplets form on the bottle and slide down, showing intense hydration.
> **[Selling Point Demonstration]**
> Begin on a macro close-up, slowly and steadily orbit while pushing in.
> **[Visual Hook and Camera Movement]**
> Following the beat of @Audio 1, a silver brand logo appears at center in the
> final two seconds. **[Audio-Visual Synchronization]**
> No flickering; the logo must not distort; droplet motion realistic.
> **[Post-Production Constraints]**

### Canonical example — Performance (diaper, pain-point hook)
> Refer to the fast camera movement and anxious expression in @Video 1 (only
> the camera/expression, not the character). Opening close-up: a young mother,
> furrowed brow, holding a crying baby, extremely anxious. **[Visual Hook: Opening]**
> At the 3-second mark the camera cuts sideways to the diaper from @Image 1.
> **[Subject]** … steam passes through the layer showing breathability.
> **[Selling Point Demonstration]** … concise, fast-paced; packaging text clear;
> faces stable. **[Post-Production Constraints]**

### Compliance red lines (enforce at prompt time)
No absolute efficacy/medical claims (use "helps look smoother"); promo/discount
claims must be real and match the landing page; disclose paid/UGC; respect
cultural/religious norms; clear IP/likeness rights; don't exaggerate demos;
human-review pricing, subtitles, logos, brand-name pronunciation.

## D. On-screen text (our hybrid decision)
Model text = short **English/number badges only** (Seedance garbles long text &
Devanagari). Hindi VO, phone, address, logo → **post overlays** (in
`overlay_text`). When model-text is OFF, the brief must include `"no subtitles"`.

## E. The `sd25-pe` skill
`sd25-pe` is an **interactive AI-chat skill** (installed via `npx skills add …`,
invoked as `/sd25-pe <prompt>`), not an API — it can't be called from the app at
runtime. Its knowledge **is** the Seedance 2.5 prompt guide, which is encoded
here and used two ways:
1. The **Script Agent** emits a `director_brief` already in the B/C structure.
2. `POST /api/optimize-prompt` runs a Seed-LLM **rewrite pass** that upgrades any
   rough prompt to this structure (the sd25-pe equivalent, callable in-app).
Users may also run `/sd25-pe` manually and paste the result into the brief box.
