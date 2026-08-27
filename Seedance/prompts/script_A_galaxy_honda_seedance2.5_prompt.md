# Galaxy Honda — "Elevate Offers" · Seedance 2.5 Prompt (≈25 s, 9:16)

Built to the official BytePlus Seedance 2.5 conventions: 6-part formula
(**subject + action + environment + camera + style + constraints**), second-level
timecodes, `Hard cut` between shots, ≤6 shots per 30 s for timecode adherence, and
`@Image` positional reference binding. Sources listed at the bottom.

**Model:** Seedance 2.5 · **Output:** 720×1280 vertical 9:16, ~25 s · **Refs:** bind
the 8 keyframe stills as `@Image1…@Image8` in the order in the legend below.

---

## 🔗 Reference legend (upload the stills in this order)

| Tag | What it controls |
|-----|------------------|
| `@Image1` | Presenter (face + wardrobe) — the recurring character |
| `@Image2` | Exterior: Galaxy Honda forecourt / facade |
| `@Image3` | Showroom entrance / interior |
| `@Image4` | Grey Honda Elevate beside presenter (ELEVATE badge) |
| `@Image5` | Presenter presenting the car's hood, showroom |
| `@Image6` | Honda Elevate driving on mountain highway (hero B-roll) |
| `@Image7` | Presenter beside Elevate, showroom (interest-rate shot) |
| `@Image8` | Elevate front grille + Honda logo close-up |

> One reference per element that must stay consistent — don't over-stack. If your run
> supports per-shot binding, bind each `@Image` to its matching shot.

---

## ✅ Copy-paste prompt

> `@Image1` is the presenter and stays identical in every live shot: a friendly Indian
> woman in her late 20s, warm medium-brown skin, bright genuine smile, long wavy dark
> hair, small gold hoop earrings, a fitted black button-up shirt with sleeves rolled to
> the forearm, a black belt with a gold buckle, and high-waisted blue jeans. The car is
> the same grey **Honda Elevate** SUV throughout. Photorealistic cinematic dealer
> commercial, natural daylight and bright showroom lighting, warm upbeat premium
> advertising look, vertical 9:16.
>
> `[0:00–0:04] MEDIUM SHOT, static eye-level` — Using `@Image2`, the presenter stands on
> the paved forecourt outside the glass-fronted "Galaxy Honda" dealership under a clear
> blue sky, one hand on her hip, the other opening in a warm welcoming gesture toward the
> showroom, smiling at camera; gentle breeze in her hair. Hard cut.
>
> `[0:04–0:09] WIDE SHOT, steadicam follow` — Using `@Image3`, she walks forward through
> the glass entrance into a bright modern showroom, confident stride, gesturing openly at
> the grey Honda Elevate and other Hondas on the polished reflective floor, warm smile;
> camera dollies smoothly with her. Hard cut.
>
> `[0:09–0:14] MEDIUM SHOT, slow push in` — Using `@Image4` and `@Image5`, she stands
> beside the front of the grey Honda Elevate, resting one hand near the hood then opening
> it back toward camera, the "ELEVATE" badge and Honda grille clearly in frame, confident
> smile; car static, headroom kept at top for a badge. Hard cut.
>
> `[0:14–0:18] WIDE TRACKING SHOT, no people` — Using `@Image6`, the grey Honda Elevate
> drives toward camera on a scenic green mountain highway with a winding road, 3/4 front
> angle, wheels rotating, trees and guardrail rushing past with motion blur, bright
> daylight, a sense of speed and freedom. Hard cut.
>
> `[0:18–0:22] MEDIUM-WIDE SHOT, static` — Using `@Image7`, back in the showroom she
> stands beside the Honda Elevate and presents it with a smooth open-hand gesture and warm
> smile, slight weight shift; space kept at top-left for a badge. Hard cut.
>
> `[0:22–0:25] CLOSE-UP, slow push in` — Using `@Image8`, a cinematic push-in on the Honda
> Elevate front grille and LED headlights, chrome Honda logo and "ELEVATE" badge, glossy
> grey paint, a subtle light glint travelling across the chrome, resolving on the emblem.
>
> **Style:** consistent photorealistic advertising grade, smooth stabilized camera, shallow
> depth of field, clean quick cuts. **Sound:** warm ambient showroom tone under an upbeat,
> confident background-music bed that builds toward the end. **Constraints:** keep the same
> woman, wardrobe and grey car in every shot; no distorted faces or hands, no warped text or
> logos, no extra fingers, no outfit or car-color change, no flicker.

*(~230 words of shot body — within the 150–250-word range for a timed multi-shot script.)*

---

## 🔤 Post-production layer (add in your editor — do NOT bake into Seedance)

Seedance warps on-screen text, so burn Hindi VO + offer badges + the brand end card in
after generation. Timings map onto the 6 shots:

| Time | On-screen graphic | Hindi VO |
|------|-------------------|----------|
| 0–2 s | Honda logo top-left · `Galaxy Honda` top-right · contact bar | नई SUV खरीदने का सोच रहे हैं? |
| 2–5.5 s | same frame | तो इस बार चुनिए — Honda Elevate। |
| 5.5–8 s | center badge **"Galaxy Honda पर मिल रहे हैं ज़बरदस्त ऑफर्स"** | और Galaxy Honda लाया है आपके लिए ज़बरदस्त ऑफर्स। |
| 8–10.5 s | top badge 💰 **₹2.45 लाख तक Cash Discount** | ₹2.45 लाख तक का cash discount। |
| 10.5–13 s | top badge 🛡️ **7 साल की Warranty – Unlimited Kilometres** | 7 साल की warranty — unlimited kilometres। |
| 13–16 s | badge **7.65% Rate of Interest** + **Zero Down Payment** | ज़ीरो डाउन पेमेंट और सिर्फ़ 7.65% ब्याज़ दर। |
| 16–17.6 s | — | फिर देर किस बात की? |
| 18–20.6 s | logo/contact frame | आज ही Galaxy Honda आइए — और Elevate घर ले जाइए। |
| 22.5–25 s | Address **NR. GURU GOBIND SINGH AVENUE, LAMBA PIND CHOWK** · 📞 **97810-97810** · Branches **Jalandhar / Hoshiarpur** | music only |

**Persistent overlays every shot:** `Ⓗ HONDA` logo top-left · `Galaxy Honda` top-right ·
bottom contact bar `📍 Galaxy Honda · Jalandhar / Hoshiarpur · 📞 97810-97810` · ✦ sparkle.

---

## Why this structure (Seedance 2.5 best-practice basis)

- **6-part formula** `subject + action + environment + camera + style + constraints`,
  first 20–30 words lock the subject/character.
- **Second-level timecodes** `[0:00–0:04]` per shot — the model is highly responsive to
  them; each shot names its **shot size + camera move** and ends on `Hard cut`.
- **≤6 shots** in a 25–30 s script (packing 4–6 shots keeps timecodes on beat; 9 was too
  many, so the original keyframes were consolidated).
- **`@Image` positional binding** — one reference per element that must stay consistent,
  with the physical description repeated in the style line.
- **One style line + one sound line** at the end; overlays/VO kept in post so text stays crisp.

Once you share the official PDF, I'll diff this against it and adjust anything specific
(exact tag syntax, negative-prompt field, per-shot reference limits).

### Sources
- BytePlus ModelArk — Dreamina Seedance 2.5 prompt guide: https://docs.byteplus.com/en/docs/ModelArk/2607689
- BytePlus ModelArk — Seedance-1.5-pro prompt guide: https://docs.byteplus.com/en/docs/ModelArk/2168087
- fal.ai — Seedance 2.5 prompting guide + real examples: https://fal.ai/learn/devs/seedance-2-5-prompting-guide
- awesome-seedance-2.5-api-prompts (formula, timecode + @Image syntax): https://github.com/Anil-matcha/awesome-seedance-2.5-api-prompts
- RunDiffusion — references, camera, story, sound: https://www.rundiffusion.com/seedance-2-5-prompt-guide
