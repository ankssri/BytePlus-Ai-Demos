# VLM_Eval — Seed 2.1 vs Gemini 3.1 (Vision-Language Evaluation)

A reproducible harness to compare **BytePlus `dola-seed-2-1-turbo-260628`** against
**`gemini-3.1-pro-preview`** on vision-language tasks — both as an **interactive web app**
and as a **batch runner that produces a shareable HTML report**.

It was built in response to a customer benchmark ("Director Agent Eval") that ranked Seed 2.1
below Gemini/Claude on a 3D spatial-staging task. The key finding there was **not raw vision
capability** — Seed's spatial numbers were competitive (det F1 0.80, IoU 0.82) — but
**reliability**: Seed returned valid JSON on only **~59%** of calls because thinking-mode
stalled (up to ~33s) and truncated the JSON. This harness gives every model a **fair shot** by
handling that plumbing explicitly, so the comparison measures vision, not JSON hygiene.

---

## What's inside

| Piece | File | Purpose |
|---|---|---|
| Provider client | `vlm_eval/providers/client.py` | One OpenAI-compatible client for **both** Seed (Ark) and Gemini, with retries, timeout, latency, and robust JSON extraction |
| 3D-director task | `vlm_eval/tasks/director3d.py` | Replicates the customer's spatial-staging benchmark with rule-based, **unit-tested** scoring |
| General tasks | `vlm_eval/tasks/general.py` | OCR / counting / chart / table / spatial VQA + open-ended (LLM-judged) |
| Datasets | `datasets/*/generate.py` | Self-contained image generators with **exact ground truth** (no downloads) |
| Runner | `vlm_eval/runner.py` | Batch execution, repeats, aggregation |
| Report | `vlm_eval/report.py` | Self-contained HTML report mirroring the customer's layout |
| Web UI | `app.py` | Streamlit: interactive side-by-side + batch report |
| CLI | `run_eval.py` | Headless batch runner |
| Tests | `tests/test_metrics.py` | 34 assertions on the scorers + JSON extraction |

---

## Setup

```bash
cd VLM_Eval
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure keys — the real .env is git-ignored and never committed.
cp .env.example .env
#   edit .env: add SEED_API_KEY, GEMINI_API_KEY (endpoints + model IDs have defaults)

# Generate the bundled datasets (images + exact ground truth)
python datasets/director3d/generate.py
python datasets/general/generate.py
```

`.env` keys:

```
SEED_API_KEY / SEED_BASE_URL / SEED_MODEL          # BytePlus Ark (OpenAI-compatible)
GEMINI_API_KEY / GEMINI_BASE_URL / GEMINI_MODEL    # Gemini OpenAI-compatible endpoint
JUDGE_PROVIDER=gemini                               # grades open-ended answers
SEED_THINKING=disabled                              # fair-shot default (see below)
REQUEST_TIMEOUT=120 / MAX_RETRIES=2
```

> **Secrets never leave `.env`.** They are read at runtime, never logged, and `.env` is in
> `.gitignore`. Do not paste keys into code or commit them.

---

## Run it

**Interactive web app**

```bash
streamlit run app.py
```
- **Compare** tab: pick/upload an image, enter a prompt, run both models side-by-side —
  see answers, latency, JSON validity, and (for director3d items) live scores vs ground truth.
- **Batch report** tab: run whole datasets, view the leaderboard, and download the HTML report.

**CLI batch + report**

```bash
python run_eval.py --dataset all --repeats 3          # -> results/report.html + results/report.json
python run_eval.py --dataset director3d               # only the spatial track
python run_eval.py --dataset all --mock               # offline pipeline demo (no keys/network)
```

**Unit tests**

```bash
python tests/test_metrics.py        # 34/34 assertions on the rule-based scorers
```

---

## The two tracks

### 1. `director3d` — the customer's spatial-staging benchmark, replicated

Each model gets an image and must return strict JSON describing every person: bounding box,
body **roll** (orientation), **facing** direction, and a **depth rank**, plus the key-light
direction. Scoring is rule-based and unit-tested:

| Metric | Meaning |
|---|---|
| `det F1` / `IoU` | predicted boxes matched to GT at IoU ≥ 0.5 |
| `roll` | orientation quadrant correct on matched people |
| `facing` | facing direction correct on matched people |
| `L→R` | pairwise left-right ordering vs GT (via matched boxes) |
| `depth` | pairwise depth ordering vs GT |
| `light` | key-light direction shares a component with GT |
| **composite** | equal-weight mean of the available sub-metrics |

The 10 bundled scenes are **synthetic** — drawn with PIL so the ground truth is *exact*, not
hand-labeled — covering `single / multi / crowd / depth / leftright / upside_down / sideways /
occlusion / facing_away`. To add **real photos**, drop them in `datasets/director3d/images/`
and add a manifest entry with hand-labeled `ground_truth.people[].box` and `track: "real"`; the
report then shows a synthetic-vs-real split.

### 2. `general` — a broad VLM suite

OCR (sign text), counting, bar-chart reading, table lookup, and spatial/colour reasoning are
scored deterministically against exact answers; one open-ended captioning item is graded 0–5 by
a judge model (`JUDGE_PROVIDER`). Extend it by editing `datasets/general/generate.py` or adding
manifest rows.

---

## Fair-shot handling (why this differs from the customer's run)

The customer's failures were dominated by Seed returning unparseable JSON under thinking-mode
stalls. This harness addresses that directly, for **both** models equally:

- **`response_format: json_object`** on structured tasks so the model is asked for machine JSON.
- **Robust extraction** — clean JSON, ```json fences, or JSON embedded in prose all parse.
- **Retries** (`MAX_RETRIES`) with a corrective "return only JSON" nudge on parse failure.
- **`SEED_THINKING=disabled`** by default for the structured track — the turbo model answers
  directly, removing the multi-second stalls; flip to `enabled`/`auto` to measure the trade-off.
- **Latency + validity are reported**, not hidden: the report's Reliability section shows JSON
  validity %, median/max latency, and score jitter across repeats, so a reliability gap is
  visible as exactly that rather than silently dragging the capability score.

The result is an apples-to-apples comparison of **spatial reasoning**, with reliability surfaced
as its own axis.

---

## Manifest schema (to add your own items)

```json
{
  "items": [
    {
      "id": "my_item",
      "task": "director3d | vqa_numeric | vqa_keyword | open_ended",
      "image": "images/my_item.png",
      "tags": ["multi", "depth"],
      "track": "synthetic | real",
      "ground_truth": { "...": "for director3d" },
      "answer": "7 | [\"accepted\", \"strings\"] | reference text",
      "meta": { "question": "...", "tolerance": 0 }
    }
  ]
}
```

## Notes & caveats

Synthetic scenes isolate spatial reasoning with exact ground truth but use stylised mannequins
(a domain gap from photos); add real, hand-labeled photos for ecological validity. The LLM judge
for open-ended items can carry self-preference bias — prefer a third-party judge when available,
or rely on the deterministic tasks for the headline numbers.
