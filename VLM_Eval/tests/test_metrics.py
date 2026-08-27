"""Unit tests for the rule-based scorers. Run: python tests/test_metrics.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vlm_eval.tasks.director3d import (  # noqa: E402
    iou, match_boxes, score_director, _pairwise_order_score, _denorm_box,
)
from vlm_eval.tasks.grounding import parse_bbox  # noqa: E402
from vlm_eval.utils import extract_json  # noqa: E402

_passed = 0
_failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
    else:
        _failed += 1
        print(f"  FAIL: {name}")


def approx(a, b, tol=1e-6):
    return a is not None and abs(a - b) <= tol


# -- IoU -------------------------------------------------------------------
check("iou identical", approx(iou([0, 0, 10, 10], [0, 0, 10, 10]), 1.0))
check("iou disjoint", approx(iou([0, 0, 10, 10], [20, 20, 30, 30]), 0.0))
check("iou half", approx(iou([0, 0, 10, 10], [5, 0, 15, 10]), 1 / 3))
check("iou unordered coords", approx(iou([10, 10, 0, 0], [0, 0, 10, 10]), 1.0))

# -- matching --------------------------------------------------------------
pred = [{"box": [0, 0, 10, 10]}, {"box": [100, 100, 110, 110]}]
gt = [{"box": [1, 1, 11, 11]}, {"box": [101, 101, 111, 111]}]
m = match_boxes(pred, gt)
check("match count", len(m) == 2)
check("no match below 0.5", len(match_boxes([{"box": [0, 0, 10, 10]}], [{"box": [8, 8, 18, 18]}])) == 0)
check("greedy no double-use", len(match_boxes(
    [{"box": [0, 0, 10, 10]}], [{"box": [0, 0, 10, 10]}, {"box": [0, 0, 10, 10]}])) == 1)

# -- pairwise ordering -----------------------------------------------------
matches = [(0, 0, 1.0), (1, 1, 1.0)]
predp = [{"x": 1}, {"x": 2}]
gtp = [{"x": 1}, {"x": 2}]
check("order preserved", approx(_pairwise_order_score(matches, predp, gtp,
      lambda p: p["x"], lambda g: g["x"]), 1.0))
check("order reversed", approx(_pairwise_order_score(matches, [{"x": 2}, {"x": 1}], gtp,
      lambda p: p["x"], lambda g: g["x"]), 0.0))
check("order none when single", _pairwise_order_score(
    [(0, 0, 1.0)], predp, gtp, lambda p: p["x"], lambda g: g["x"]) is None)

# -- full director scoring -------------------------------------------------
GT = {
    "image_width": 1024, "image_height": 768,
    "people": [
        {"box": [100, 100, 200, 400], "orientation": "upright", "facing": "left", "depth_rank": 0},
        {"box": [600, 100, 700, 380], "orientation": "upside_down", "facing": "right", "depth_rank": 1},
    ],
    "light_direction": "left",
}

perfect = {
    "people": [
        {"box": [100, 100, 200, 400], "orientation": "upright", "facing": "left", "depth_rank": 0},
        {"box": [600, 100, 700, 380], "orientation": "upside_down", "facing": "right", "depth_rank": 1},
    ],
    "light_direction": "left",
}
mp, notes = score_director(perfect, GT)
check("perfect det_f1", approx(mp["det_f1"], 1.0))
check("perfect iou", approx(mp["iou"], 1.0))
check("perfect roll", approx(mp["roll"], 1.0))
check("perfect facing", approx(mp["facing"], 1.0))
check("perfect leftright", approx(mp["leftright"], 1.0))
check("perfect depth", approx(mp["depth"], 1.0))
check("perfect light", approx(mp["light"], 1.0))
check("perfect no notes", notes == [])

# missing a person
missing = {"people": [perfect["people"][0]], "light_direction": "left"}
mm, notes = score_director(missing, GT)
check("missing recall lowers f1", mm["det_f1"] < 1.0)
check("missing note", "missed a person" in notes)

# phantom detection
phantom = {"people": perfect["people"] + [{"box": [900, 500, 950, 700],
           "orientation": "upright", "facing": "left", "depth_rank": 2}],
           "light_direction": "left"}
mph, notes = score_director(phantom, GT)
check("phantom note", "phantom detection" in notes)
check("phantom precision drop", mph["det_f1"] < 1.0)

# wrong light + wrong orientation
bad = {
    "people": [
        {"box": [100, 100, 200, 400], "orientation": "upside_down", "facing": "left", "depth_rank": 0},
        {"box": [600, 100, 700, 380], "orientation": "upside_down", "facing": "right", "depth_rank": 1},
    ],
    "light_direction": "right",
}
mb, notes = score_director(bad, GT)
check("wrong light zero", approx(mb["light"], 0.0))
check("half roll", approx(mb["roll"], 0.5))
check("orientation note", "orientation wrong" in notes)
check("light note", "light direction off" in notes)

# depth reversed
depth_rev = {
    "people": [
        {"box": [100, 100, 200, 400], "orientation": "upright", "facing": "left", "depth_rank": 1},
        {"box": [600, 100, 700, 380], "orientation": "upside_down", "facing": "right", "depth_rank": 0},
    ],
    "light_direction": "left",
}
md, _ = score_director(depth_rev, GT)
check("depth reversed zero", approx(md["depth"], 0.0))

# empty prediction
me, notes = score_director({"people": []}, GT)
check("empty det_f1 zero", approx(me["det_f1"], 0.0))

# -- coordinate denormalization (0-1000 grid -> pixels) --------------------
check("denorm full", _denorm_box([0, 0, 1000, 1000], 1000, 800, 600) == [0, 0, 800, 600])
check("denorm half", _denorm_box([500, 500, 1000, 1000], 1000, 800, 600) == [400, 300, 800, 600])

# Normalized prediction (0-1000) matched against pixel GT via pred_coord_scale.
GT_N = {
    "image_width": 1000, "image_height": 1000,
    "people": [{"box": [100, 100, 200, 400], "orientation": "upright",
                "facing": "left", "depth_rank": 0}],
    "light_direction": "left",
}
norm_pred = {"people": [{"box": [100, 100, 200, 400], "orientation": "upright",
             "facing": "left", "depth_rank": 0}], "light_direction": "left"}
mn, _ = score_director(norm_pred, GT_N, pred_coord_scale=1000)
check("normalized perfect on square image", approx(mn["det_f1"], 1.0) and approx(mn["iou"], 1.0))

# A pixel-scale prediction WITHOUT denorm would mismatch a 1000-grid GT;
# with denorm on a non-square image the mapping still lands on GT.
GT_NS = {
    "image_width": 1024, "image_height": 768,
    "people": [{"box": [512, 384, 768, 576], "orientation": "upright",
                "facing": "left", "depth_rank": 0}],
    "light_direction": "left",
}
norm_pred2 = {"people": [{"box": [500, 500, 750, 750], "orientation": "upright",
              "facing": "left", "depth_rank": 0}], "light_direction": "left"}
mns, _ = score_director(norm_pred2, GT_NS, pred_coord_scale=1000)
check("normalized non-square matches", mns["iou"] > 0.9)

# -- grounding bbox parsing ------------------------------------------------
check("bbox tag", parse_bbox("<bbox>10 20 30 40</bbox>") == [10, 20, 30, 40])
check("bbox tag spaced", parse_bbox("here: <bbox>  1 2 3 4 </bbox> done") == [1, 2, 3, 4])
check("bbox bare ints", parse_bbox("box is 100 200 300 400") == [100, 200, 300, 400])
check("bbox none", parse_bbox("no numbers here") is None)
check("bbox too few", parse_bbox("only 1 2") is None)

# -- JSON extraction -------------------------------------------------------
check("json clean", extract_json('{"a": 1}') == {"a": 1})
check("json fenced", extract_json('```json\n{"a": 1}\n```') == {"a": 1})
check("json in prose", extract_json('Here it is: {"a": [1,2]} done') == {"a": [1, 2]})
check("json array", extract_json("[1, 2, 3]") == [1, 2, 3])
check("json none", extract_json("no json here") is None)
check("json nested braces", extract_json('{"a": {"b": 2}} trailing') == {"a": {"b": 2}})


print(f"\n{_passed}/{_passed + _failed} passed")
sys.exit(1 if _failed else 0)
