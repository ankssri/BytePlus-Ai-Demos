"""3D scene-director task — replicates the customer's spatial-staging benchmark.

Each model receives an image and must return a strict JSON description of every
person: bounding box, body roll (orientation), which way they face, and a depth
rank. Scoring is rule-based and unit-tested, mirroring the customer's metrics:

  det F1 / IoU  boxes matched to ground truth at IoU >= 0.5
  roll          orientation quadrant correct on matched people
  facing        facing direction correct on matched people
  L->R          pairwise left-right ordering vs GT (via matched boxes)
  depth         pairwise depth ordering vs GT (via matched boxes)
  light         key-light direction shares a component with GT
  composite     equal-weight mean of the available sub-metrics
"""
from __future__ import annotations

from typing import Any, Optional

from ..providers import ChatClient
from .base import EvalItem, ItemScore, Task

IOU_MATCH = 0.5
# Models return box coordinates on a normalized 0-1000 grid — this is Seed's
# native visual-grounding convention (coords normalized to 1000x1000), which
# Gemini follows from the explicit instruction. The scorer denormalizes to
# pixels before matching against ground truth, so no model is penalized for a
# coordinate-scale mismatch (a likely hidden cause of the customer's low IoU).
COORD_SCALE = 1000

# Strict JSON schema (BytePlus Structured Output / json_schema mode). Enums +
# required + additionalProperties:false make malformed or missing fields
# impossible, which is the direct fix for Seed's ~59% valid-JSON rate.
DIRECTOR_SCHEMA = {
    "type": "object",
    "properties": {
        "people": {
            "type": "array",
            "description": "Every person visible in the image.",
            "items": {
                "type": "object",
                "properties": {
                    "box": {
                        "type": "array",
                        "description": "Bounding box [x1,y1,x2,y2] on a 0-1000 grid, origin top-left.",
                        "items": {"type": "integer"},
                    },
                    "orientation": {
                        "type": "string",
                        "description": "Body roll: upright=head up, upside_down=head down, left/right=rotated 90deg toward that side.",
                        "enum": ["upright", "upside_down", "left", "right"],
                    },
                    "facing": {
                        "type": "string",
                        "description": "Direction the person faces from the camera's view.",
                        "enum": ["left", "right", "toward", "away"],
                    },
                    "depth_rank": {
                        "type": "integer",
                        "description": "0 = nearest the camera, larger integers = farther away.",
                    },
                },
                "required": ["box", "orientation", "facing", "depth_rank"],
                "additionalProperties": False,
            },
        },
        "light_direction": {
            "type": "string",
            "description": "Dominant key-light direction.",
            "enum": ["left", "right", "top", "bottom", "front"],
        },
    },
    "required": ["people", "light_direction"],
    "additionalProperties": False,
}

# With json_schema enforcing structure, the prompt describes only the task /
# semantics (per BytePlus prompt guidance: don't restate the output format).
_PROMPT = """You are a 3D scene director analysing a photograph ({w} x {h} pixels).
Detect every person and stage the scene: for each person give a bounding box on
a 0-1000 normalized grid (origin top-left), the body roll (orientation), the
direction they face, and a depth rank where 0 is nearest the camera. Also report
the dominant key-light direction."""


class Director3DTask(Task):
    name = "director3d"
    expect_json = True

    def default_prompt(self, item: EvalItem) -> str:
        gt = item.ground_truth or {}
        return _PROMPT.format(w=gt.get("image_width", 1024), h=gt.get("image_height", 768))

    def run(self, client: ChatClient, item: EvalItem, judge: Optional[ChatClient] = None) -> ItemScore:
        prompt = item.prompt or self.default_prompt(item)
        res = client.chat(
            prompt,
            image_paths=[item.image_path],
            expect_json=True,
            json_schema=DIRECTOR_SCHEMA,
            schema_name="scene_director",
            max_tokens=1500,
        )
        if not res.ok or not res.json_valid:
            note = res.error or "invalid/empty JSON"
            return ItemScore(composite=None, metrics={}, valid=False,
                             latency_s=res.latency_s, attempts=res.attempts,
                             error=note, notes=["invalid/empty JSON"], raw_text=res.text)

        pred = res.json_obj
        metrics, notes = score_director(pred, item.ground_truth, pred_coord_scale=COORD_SCALE)
        composite = _mean([metrics[k] for k in metrics if metrics[k] is not None]) if metrics else None
        return ItemScore(
            composite=composite,
            metrics=metrics,
            valid=True,
            latency_s=res.latency_s,
            attempts=res.attempts,
            notes=notes,
            prediction=pred,
            raw_text=res.text,
        )


# --------------------------------------------------------------------------- #
# Pure scoring functions (unit-tested in tests/test_metrics.py)
# --------------------------------------------------------------------------- #
def iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = _norm_box(a)
    bx1, by1, bx2, by2 = _norm_box(b)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _norm_box(b) -> list[float]:
    x1, y1, x2, y2 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
    return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]


def _denorm_box(b, scale: float, w: float, h: float) -> list[float]:
    """Map a box on a 0-`scale` grid to absolute pixels for image (w, h)."""
    try:
        return [b[0] / scale * w, b[1] / scale * h, b[2] / scale * w, b[3] / scale * h]
    except (TypeError, ZeroDivisionError, IndexError):
        return [0.0, 0.0, 0.0, 0.0]


def match_boxes(pred: list[dict], gt: list[dict]) -> list[tuple[int, int, float]]:
    """Greedy IoU matching. Returns list of (pred_idx, gt_idx, iou)."""
    pairs = []
    for pi, p in enumerate(pred):
        for gi, g in enumerate(gt):
            if "box" in p and "box" in g:
                pairs.append((iou(p["box"], g["box"]), pi, gi))
    pairs.sort(reverse=True)
    used_p, used_g, matches = set(), set(), []
    for i, pi, gi in pairs:
        if i < IOU_MATCH or pi in used_p or gi in used_g:
            continue
        used_p.add(pi)
        used_g.add(gi)
        matches.append((pi, gi, i))
    return matches


def _pairwise_order_score(matches, pred, gt, key_pred, key_gt) -> Optional[float]:
    """Fraction of GT pairs whose ordering is preserved in the prediction."""
    if len(matches) < 2:
        return None
    total, correct = 0, 0
    for a in range(len(matches)):
        for b in range(a + 1, len(matches)):
            pa, ga, _ = matches[a]
            pb, gb, _ = matches[b]
            gva, gvb = key_gt(gt[ga]), key_gt(gt[gb])
            if gva == gvb:
                continue  # no defined GT order for this pair
            pva, pvb = key_pred(pred[pa]), key_pred(pred[pb])
            total += 1
            gt_less = gva < gvb
            pred_less = pva < pvb
            if gt_less == pred_less:
                correct += 1
    if total == 0:
        return None
    return correct / total


def _center_x(box) -> float:
    b = _norm_box(box)
    return (b[0] + b[2]) / 2.0


def score_director(pred: Any, ground_truth: dict,
                   pred_coord_scale: Optional[float] = None) -> tuple[dict, list[str]]:
    """Return (metrics dict, human-readable error notes).

    ``pred_coord_scale`` denormalizes predicted box coordinates before matching:
    when set (e.g. 1000), each predicted coordinate is mapped to pixels via
    ``coord / scale * image_dim`` using the GT image size. This lets models
    return coordinates on their native 0-1000 grid without being penalized.
    """
    notes: list[str] = []
    gt = ground_truth or {}
    gt_people = gt.get("people", [])
    if isinstance(pred, dict):
        pred_people = pred.get("people", [])
    elif isinstance(pred, list):
        pred_people = pred
    else:
        pred_people = []
    pred_people = [p for p in pred_people if isinstance(p, dict) and "box" in p]

    if pred_coord_scale:
        w = gt.get("image_width", pred_coord_scale)
        h = gt.get("image_height", pred_coord_scale)
        pred_people = [{**p, "box": _denorm_box(p["box"], pred_coord_scale, w, h)}
                       for p in pred_people]

    matches = match_boxes(pred_people, gt_people)
    n_match = len(matches)
    n_pred, n_gt = len(pred_people), len(gt_people)

    precision = n_match / n_pred if n_pred else 0.0
    recall = n_match / n_gt if n_gt else 0.0
    det_f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    mean_iou = _mean([m[2] for m in matches]) if matches else 0.0

    if n_match < n_gt:
        notes.append("missed a person")
    if n_pred > n_match:
        notes.append("phantom detection")

    # roll / facing on matched people
    def _quad_score(key: str, wrong_note: str) -> Optional[float]:
        if not matches:
            return None
        ok = 0
        any_wrong = False
        for pi, gi, _ in matches:
            pv = str(pred_people[pi].get(key, "")).lower()
            gv = str(gt_people[gi].get(key, "")).lower()
            if pv == gv:
                ok += 1
            else:
                any_wrong = True
        if any_wrong:
            notes.append(wrong_note)
        return ok / len(matches)

    roll = _quad_score("orientation", "orientation wrong")
    facing = _quad_score("facing", "facing wrong")

    leftright = _pairwise_order_score(
        matches, pred_people, gt_people,
        key_pred=lambda p: _center_x(p["box"]),
        key_gt=lambda g: _center_x(g["box"]),
    )
    depth = _pairwise_order_score(
        matches, pred_people, gt_people,
        key_pred=lambda p: _as_int(p.get("depth_rank", 0)),
        key_gt=lambda g: _as_int(g.get("depth_rank", 0)),
    )
    if depth is not None and depth < 1.0:
        notes.append("depth order off")

    light = _light_score(pred, ground_truth, notes)

    metrics = {
        "det_f1": det_f1,
        "iou": mean_iou,
        "roll": roll,
        "facing": facing,
        "leftright": leftright,
        "depth": depth,
        "light": light,
    }
    return metrics, notes


def _light_score(pred: Any, gt: dict, notes: list[str]) -> Optional[float]:
    gt_light = str((gt or {}).get("light_direction", "")).lower().strip()
    if not gt_light:
        return None
    pred_light = ""
    if isinstance(pred, dict):
        pred_light = str(pred.get("light_direction", "")).lower().strip()
    if not pred_light:
        notes.append("light direction off")
        return 0.0
    gt_tokens = set(gt_light.replace("-", " ").split())
    pred_tokens = set(pred_light.replace("-", " ").split())
    if gt_tokens & pred_tokens:
        return 1.0
    notes.append("light direction off")
    return 0.0


def _as_int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _mean(values: list[float]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None
