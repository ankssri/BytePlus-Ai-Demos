"""Generate synthetic visual-grounding scenes with exact target boxes.

Each image places a uniquely describable target shape (plus distractors) at a
known pixel bounding box. The model is asked to return the target's box in the
native `<bbox>` 0-1000 format; the harness denormalizes and scores IoU.

Run:  python datasets/grounding/generate.py
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
IMG_DIR = HERE / "images"
W, H = 1024, 768


def _new():
    img = Image.new("RGB", (W, H), (245, 246, 248))
    return img, ImageDraw.Draw(img)


def _circle(d, box, fill):
    d.ellipse(box, fill=fill)


def _square(d, box, fill):
    d.rectangle(box, fill=fill)


def _triangle(d, box, fill):
    x1, y1, x2, y2 = box
    d.polygon([(x1, y2), ((x1 + x2) / 2, y1), (x2, y2)], fill=fill)


def item(id_, target, box, draw_fn):
    return {"id": id_, "task": "grounding", "image": f"images/{id_}.png",
            "tags": ["grounding"], "track": "synthetic",
            "ground_truth": {"box": [int(v) for v in box], "image_width": W, "image_height": H},
            "meta": {"target": target}}


def build() -> list[dict]:
    items = []

    # 1. red circle (distractor: blue square)
    img, d = _new()
    _square(d, [120, 150, 260, 290], (50, 90, 220))
    box = [640, 300, 820, 480]
    _circle(d, box, (220, 40, 40))
    img.save(IMG_DIR / "gr01_red_circle.png")
    items.append(item("gr01_red_circle", "the red circle", box, None))

    # 2. blue square (distractors: red circle, green triangle)
    img, d = _new()
    _circle(d, [700, 120, 840, 260], (220, 40, 40))
    _triangle(d, [120, 480, 300, 640], (40, 160, 70))
    box = [420, 300, 600, 480]
    _square(d, box, (40, 90, 220))
    img.save(IMG_DIR / "gr02_blue_square.png")
    items.append(item("gr02_blue_square", "the blue square", box, None))

    # 3. green triangle (distractor: orange circle)
    img, d = _new()
    _circle(d, [140, 160, 300, 320], (230, 150, 30))
    box = [560, 360, 780, 600]
    _triangle(d, box, (40, 160, 70))
    img.save(IMG_DIR / "gr03_green_triangle.png")
    items.append(item("gr03_green_triangle", "the green triangle", box, None))

    # 4. yellow circle on the RIGHT (two yellow circles; spatial disambiguation)
    img, d = _new()
    _circle(d, [150, 320, 310, 480], (235, 205, 40))       # left
    box = [700, 320, 860, 480]                             # right (target)
    _circle(d, box, (235, 205, 40))
    img.save(IMG_DIR / "gr04_right_yellow.png")
    items.append(item("gr04_right_yellow", "the yellow circle on the right", box, None))

    # 5. small purple square among larger shapes (size/colour disambiguation)
    img, d = _new()
    _circle(d, [120, 120, 360, 360], (90, 90, 90))
    _triangle(d, [640, 360, 900, 640], (200, 120, 60))
    box = [470, 200, 560, 290]
    _square(d, box, (150, 60, 200))
    img.save(IMG_DIR / "gr05_purple_square.png")
    items.append(item("gr05_purple_square", "the small purple square", box, None))

    return items


def main() -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    items = build()
    manifest = {"name": "grounding-synthetic",
                "description": "Visual grounding scenes with exact target boxes.",
                "items": items}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {len(items)} grounding items to {IMG_DIR} and manifest.json")


if __name__ == "__main__":
    main()
