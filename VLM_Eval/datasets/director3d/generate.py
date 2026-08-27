"""Generate synthetic 3D-director scenes with EXACT ground truth.

Each scene draws simple mannequin figures at known positions, orientations
(roll), facing directions, and depths, on a background whose gradient + drop
shadows encode a known key-light direction. Because we control the geometry,
the ground-truth bounding boxes and labels are exact — no hand labeling.

Run:  python datasets/director3d/generate.py
Produces images/*.png and manifest.json next to this file.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
IMG_DIR = HERE / "images"
W, H = 1024, 768

# Orientation (body roll) -> rotation angle applied to an upright figure.
ROLL_ANGLE = {"upright": 0, "left": 90, "right": -90, "upside_down": 180}


def _draw_mannequin(size: int, facing: str, color=(70, 90, 120)) -> Image.Image:
    """Draw an upright grey mannequin on a transparent tile, facing `facing`."""
    tile_w, tile_h = size, int(size * 2.2)
    img = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = tile_w // 2
    head_r = size // 3
    head_cy = head_r + 4
    # Head
    d.ellipse([cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r],
              fill=color)
    # Torso
    torso_top = head_cy + head_r
    torso_bot = torso_top + int(size * 0.9)
    d.rounded_rectangle([cx - size // 3, torso_top, cx + size // 3, torso_bot],
                        radius=size // 6, fill=color)
    # Legs
    leg_bot = torso_bot + int(size * 0.9)
    d.line([cx - size // 6, torso_bot, cx - size // 5, leg_bot], fill=color, width=max(4, size // 8))
    d.line([cx + size // 6, torso_bot, cx + size // 5, leg_bot], fill=color, width=max(4, size // 8))
    # Arms
    d.line([cx - size // 3, torso_top + 6, cx - size // 2, torso_top + size // 2],
           fill=color, width=max(4, size // 9))
    d.line([cx + size // 3, torso_top + 6, cx + size // 2, torso_top + size // 2],
           fill=color, width=max(4, size // 9))
    # Facing cue on the head.
    face = (245, 220, 180)
    if facing == "toward":
        # two eyes
        d.ellipse([cx - head_r // 2 - 3, head_cy - 3, cx - head_r // 2 + 3, head_cy + 3], fill=face)
        d.ellipse([cx + head_r // 2 - 3, head_cy - 3, cx + head_r // 2 + 3, head_cy + 3], fill=face)
    elif facing == "away":
        pass  # back of the head — no face features
    elif facing == "left":
        d.polygon([(cx - head_r, head_cy), (cx - head_r // 3, head_cy - 5),
                   (cx - head_r // 3, head_cy + 5)], fill=face)  # nose points left
    elif facing == "right":
        d.polygon([(cx + head_r, head_cy), (cx + head_r // 3, head_cy - 5),
                   (cx + head_r // 3, head_cy + 5)], fill=face)  # nose points right
    return img


def _background(light: str) -> Image.Image:
    """Gradient background brighter toward the light direction."""
    bg = Image.new("RGB", (W, H))
    px = bg.load()
    base, span = 150, 90
    for y in range(H):
        for x in range(W):
            if light == "left":
                t = 1 - x / W
            elif light == "right":
                t = x / W
            elif light == "top":
                t = 1 - y / H
            elif light == "bottom":
                t = y / H
            else:  # front / ambient
                t = 0.5
            v = int(base + span * t)
            px[x, y] = (v, v, min(255, v + 10))
    return bg


def _shadow_offset(light: str) -> tuple[int, int]:
    return {
        "left": (18, 10), "right": (-18, 10),
        "top": (0, 20), "bottom": (0, -20), "front": (8, 12),
    }.get(light, (8, 12))


def render_scene(spec: dict) -> dict:
    """Render one scene, returning its manifest entry with EXACT ground truth."""
    light = spec["light_direction"]
    scene = _background(light).convert("RGBA")
    sox, soy = _shadow_offset(light)

    # Draw farthest first so nearer figures occlude them (depth via draw order).
    people = sorted(spec["people"], key=lambda p: -p["depth_rank"])
    gt_people = []
    for person in people:
        size = person["size"]
        tile = _draw_mannequin(size, person["facing"])
        angle = ROLL_ANGLE[person["orientation"]]
        if angle:
            tile = tile.rotate(angle, expand=True)
        cx, cy = person["cx"], person["cy"]
        ox, oy = cx - tile.width // 2, cy - tile.height // 2

        # Drop shadow.
        alpha = tile.split()[-1]
        shadow = Image.new("RGBA", tile.size, (0, 0, 0, 0))
        shadow.putalpha(alpha.point(lambda a: int(a * 0.35)))
        scene.alpha_composite(shadow, (ox + sox, oy + soy))
        scene.alpha_composite(tile, (ox, oy))

        # Exact GT box from this figure's alpha bbox in scene coordinates.
        bbox = alpha.getbbox()
        x1, y1, x2, y2 = bbox
        gt_people.append({
            "id": person["id"],
            "box": [ox + x1, oy + y1, ox + x2, oy + y2],
            "orientation": person["orientation"],
            "facing": person["facing"],
            "depth_rank": person["depth_rank"],
        })

    out = IMG_DIR / f"{spec['id']}.png"
    scene.convert("RGB").save(out)
    return {
        "id": spec["id"],
        "task": "director3d",
        "image": f"images/{spec['id']}.png",
        "tags": spec["tags"],
        "track": "synthetic",
        "ground_truth": {
            "image_width": W,
            "image_height": H,
            "people": gt_people,
            "light_direction": light,
        },
    }


def scene_specs() -> list[dict]:
    """10 scenes covering each capability the customer benchmark exercised."""
    return [
        {"id": "s01_single_upright", "tags": ["single"], "light_direction": "left",
         "people": [{"id": "A", "cx": 512, "cy": 384, "size": 110,
                     "orientation": "upright", "facing": "toward", "depth_rank": 0}]},
        {"id": "s02_single_upsidedown", "tags": ["single", "upside_down"], "light_direction": "right",
         "people": [{"id": "A", "cx": 512, "cy": 380, "size": 110,
                     "orientation": "upside_down", "facing": "toward", "depth_rank": 0}]},
        {"id": "s03_single_sideways", "tags": ["single", "sideways"], "light_direction": "top",
         "people": [{"id": "A", "cx": 512, "cy": 384, "size": 110,
                     "orientation": "left", "facing": "left", "depth_rank": 0}]},
        {"id": "s04_two_depth", "tags": ["multi", "depth"], "light_direction": "left",
         "people": [
             {"id": "A", "cx": 380, "cy": 430, "size": 130, "orientation": "upright", "facing": "toward", "depth_rank": 0},
             {"id": "B", "cx": 660, "cy": 360, "size": 80, "orientation": "upright", "facing": "toward", "depth_rank": 1}]},
        {"id": "s05_two_leftright", "tags": ["multi", "leftright"], "light_direction": "right",
         "people": [
             {"id": "A", "cx": 300, "cy": 400, "size": 110, "orientation": "upright", "facing": "right", "depth_rank": 0},
             {"id": "B", "cx": 720, "cy": 400, "size": 110, "orientation": "upright", "facing": "left", "depth_rank": 0}]},
        {"id": "s06_three_mixed", "tags": ["multi", "depth", "crowd"], "light_direction": "top",
         "people": [
             {"id": "A", "cx": 260, "cy": 440, "size": 130, "orientation": "upright", "facing": "toward", "depth_rank": 0},
             {"id": "B", "cx": 520, "cy": 380, "size": 100, "orientation": "upright", "facing": "left", "depth_rank": 1},
             {"id": "C", "cx": 760, "cy": 340, "size": 78, "orientation": "upright", "facing": "away", "depth_rank": 2}]},
        {"id": "s07_two_one_inverted", "tags": ["multi", "upside_down", "depth"], "light_direction": "left",
         "people": [
             {"id": "A", "cx": 360, "cy": 400, "size": 120, "orientation": "upright", "facing": "toward", "depth_rank": 0},
             {"id": "B", "cx": 680, "cy": 380, "size": 95, "orientation": "upside_down", "facing": "toward", "depth_rank": 1}]},
        {"id": "s08_four_crowd", "tags": ["multi", "crowd", "depth"], "light_direction": "right",
         "people": [
             {"id": "A", "cx": 220, "cy": 450, "size": 120, "orientation": "upright", "facing": "right", "depth_rank": 0},
             {"id": "B", "cx": 440, "cy": 410, "size": 100, "orientation": "upright", "facing": "toward", "depth_rank": 1},
             {"id": "C", "cx": 640, "cy": 370, "size": 84, "orientation": "upright", "facing": "toward", "depth_rank": 2},
             {"id": "D", "cx": 820, "cy": 340, "size": 70, "orientation": "upright", "facing": "left", "depth_rank": 3}]},
        {"id": "s09_occlusion", "tags": ["multi", "occlusion", "depth"], "light_direction": "left",
         "people": [
             {"id": "A", "cx": 470, "cy": 430, "size": 140, "orientation": "upright", "facing": "toward", "depth_rank": 0},
             {"id": "B", "cx": 560, "cy": 410, "size": 110, "orientation": "upright", "facing": "toward", "depth_rank": 1}]},
        {"id": "s10_single_highcam", "tags": ["single"], "light_direction": "bottom",
         "people": [{"id": "A", "cx": 512, "cy": 430, "size": 100,
                     "orientation": "upright", "facing": "away", "depth_rank": 0}]},
    ]


def main() -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    entries = [render_scene(spec) for spec in scene_specs()]
    manifest = {
        "name": "director3d-synthetic",
        "description": "Synthetic 3D-staging scenes with exact ground truth.",
        "items": entries,
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {len(entries)} scenes to {IMG_DIR} and manifest.json")


if __name__ == "__main__":
    main()
