"""Visual grounding task — exercises Seed's native `<bbox>` capability.

Per the BytePlus Visual Grounding docs, Seed returns a target's location as
``<bbox>x_min y_min x_max y_max</bbox>`` with coordinates **normalized to a
0-999 (1000x1000) grid**. A harness that assumes absolute pixels would score
these boxes as wildly wrong — a plausible hidden cause of Seed's low IoU in the
customer benchmark. This task requests that native format from both models and
denormalizes 0-1000 -> pixels before scoring, so grounding is measured fairly.

Ground truth per item:
    {"box": [x1,y1,x2,y2] in pixels, "image_width": W, "image_height": H}
    meta: {"target": "the red circle"}
"""
from __future__ import annotations

import re
from typing import Optional

from ..providers import ChatClient
from .base import EvalItem, ItemScore, Task
from .director3d import iou

GROUND_SCALE = 1000  # coordinates are on a 0-1000 normalized grid
_BBOX_RE = re.compile(r"<bbox>\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s*</bbox>", re.I)
_INTS_RE = re.compile(r"-?\d+")

_PROMPT = ("Draw a bounding box around {target} and output ONLY the coordinates "
           "in the format <bbox>x_min y_min x_max y_max</bbox>, where coordinates "
           "are normalized to a 0-1000 grid with the origin at the top-left.")


class GroundingTask(Task):
    name = "grounding"
    expect_json = False

    def default_prompt(self, item: EvalItem) -> str:
        target = item.meta.get("target", "the main object")
        return _PROMPT.format(target=target)

    def run(self, client: ChatClient, item: EvalItem, judge: Optional[ChatClient] = None) -> ItemScore:
        prompt = item.prompt or self.default_prompt(item)
        res = client.chat(prompt, image_paths=[item.image_path], max_tokens=128)
        if not res.ok:
            return ItemScore(None, {}, False, res.latency_s, res.attempts,
                             error=res.error, notes=["call failed"], raw_text=res.text)

        box = parse_bbox(res.text)
        if box is None:
            return ItemScore(0.0, {"iou": 0.0, "hit": 0.0}, True, res.latency_s,
                             res.attempts, notes=["no <bbox> parsed"], raw_text=res.text)

        gt = item.ground_truth or {}
        w = gt.get("image_width", GROUND_SCALE)
        h = gt.get("image_height", GROUND_SCALE)
        px = [box[0] / GROUND_SCALE * w, box[1] / GROUND_SCALE * h,
              box[2] / GROUND_SCALE * w, box[3] / GROUND_SCALE * h]
        score = iou(px, gt["box"])
        hit = 1.0 if score >= 0.5 else 0.0
        notes = [] if hit else [f"IoU {score:.2f} < 0.5"]
        return ItemScore(
            composite=score, metrics={"iou": score, "hit": hit}, valid=True,
            latency_s=res.latency_s, attempts=res.attempts, notes=notes,
            prediction={"box_px": [round(v) for v in px]}, raw_text=res.text,
        )


# Ready-to-use prompt template for Seed's native 3D detection (`<3dbbox>`).
# This is the customer's "3D director" use case done natively. Full metric
# scoring needs camera intrinsics + 3D ground truth, so this is provided as a
# documented extension you can drop into a custom task.
SEED_3DBBOX_PROMPT_TEMPLATE = (
    "The following are the detailed camera parameters of this image.\n"
    "Camera intrinsics: focal length f_x={fx}, f_y={fy}. Principal point "
    "c_x={cx}, c_y={cy} for image width {w} and height {h}. No distortion.\n"
    "Camera coordinate system: X right, Y down, Z forward; origin at the camera; "
    "camera extrinsic matrix is identity.\n"
    "Please output each 3D box as "
    "<3dbbox>x_center y_center z_center x_size y_size z_size pitch yaw roll</3dbbox>.\n"
    "Notes: centers/sizes in meters; pitch/yaw/roll are Euler angles normalized "
    "to (-1,1) (multiply by 180 for degrees). Detect {target} in this image."
)


def parse_bbox(text: str) -> Optional[list[int]]:
    """Extract 4 box coords from a `<bbox>` tag, JSON array, or bare integers."""
    if not text:
        return None
    m = _BBOX_RE.search(text)
    if m:
        return [int(x) for x in m.groups()]
    ints = _INTS_RE.findall(text)
    if len(ints) >= 4:
        return [int(x) for x in ints[:4]]
    return None
