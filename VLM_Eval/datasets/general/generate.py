"""Generate a small self-contained general-VLM dataset with exact answers.

Covers OCR, counting, chart reading, table lookup, spatial/colour reasoning,
and one open-ended captioning item (graded by an LLM judge). No downloads.

Run:  python datasets/general/generate.py
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
IMG_DIR = HERE / "images"
W, H = 900, 600


def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1 scalable default
    except TypeError:  # pragma: no cover
        return ImageFont.load_default()


def _centered(d, box, text, font, fill):
    x1, y1, x2, y2 = box
    tw = d.textlength(text, font=font)
    th = font.size
    d.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2), text, font=font, fill=fill)


def ocr_sign() -> dict:
    img = Image.new("RGB", (W, H), (30, 30, 40))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([150, 200, 750, 400], radius=20, fill=(200, 40, 40))
    _centered(d, [150, 200, 750, 400], "GATE 12 CLOSED", _font(64), (255, 255, 255))
    img.save(IMG_DIR / "g01_ocr_sign.png")
    return {"id": "g01_ocr_sign", "task": "vqa_keyword", "image": "images/g01_ocr_sign.png",
            "tags": ["ocr"], "track": "synthetic", "answer": ["gate 12 closed"],
            "meta": {"question": "What exact text is written on the sign?"}}


def counting() -> dict:
    img = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(img)
    # 7 red circles + distractor blue squares.
    reds = [(120, 120), (300, 150), (500, 110), (680, 180),
            (200, 350), (420, 400), (620, 360)]
    for (x, y) in reds:
        d.ellipse([x, y, x + 70, y + 70], fill=(220, 40, 40))
    for (x, y) in [(160, 250), (760, 300), (380, 250), (700, 460)]:
        d.rectangle([x, y, x + 60, y + 60], fill=(40, 80, 220))
    img.save(IMG_DIR / "g02_count.png")
    return {"id": "g02_count", "task": "vqa_numeric", "image": "images/g02_count.png",
            "tags": ["counting"], "track": "synthetic", "answer": 7,
            "meta": {"question": "How many red circles are in the image?", "tolerance": 0}}


def bar_chart() -> dict:
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    data = [("A", 120), ("B", 260), ("C", 180), ("D", 340), ("E", 90)]
    base_y, x = 500, 120
    for label, val in data:
        d.rectangle([x, base_y - val, x + 90, base_y], fill=(60, 110, 200))
        _centered(d, [x, base_y + 5, x + 90, base_y + 45], label, _font(30), (0, 0, 0))
        x += 150
    d.line([90, base_y, 860, base_y], fill=(0, 0, 0), width=3)
    img.save(IMG_DIR / "g03_barchart.png")
    return {"id": "g03_barchart", "task": "vqa_keyword", "image": "images/g03_barchart.png",
            "tags": ["chart"], "track": "synthetic", "answer": ["d"],
            "meta": {"question": "Which labelled bar (A-E) is the tallest? Answer with the letter."}}


def table_lookup() -> dict:
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    rows = [("City", "Population"), ("Oslo", "700000"),
            ("Lima", "9800000"), ("Cairo", "10200000"), ("Tokyo", "13900000")]
    y = 120
    for i, (a, b) in enumerate(rows):
        fill = (220, 220, 220) if i == 0 else (255, 255, 255)
        d.rectangle([150, y, 750, y + 70], fill=fill, outline=(0, 0, 0), width=2)
        d.line([450, y, 450, y + 70], fill=(0, 0, 0), width=2)
        f = _font(34)
        d.text((170, y + 18), a, font=f, fill=(0, 0, 0))
        d.text((470, y + 18), b, font=f, fill=(0, 0, 0))
        y += 70
    img.save(IMG_DIR / "g04_table.png")
    return {"id": "g04_table", "task": "vqa_keyword", "image": "images/g04_table.png",
            "tags": ["table", "ocr"], "track": "synthetic", "answer": ["9800000", "9,800,000"],
            "meta": {"question": "According to the table, what is the population of Lima?"}}


def spatial_color() -> dict:
    img = Image.new("RGB", (W, H), (250, 250, 250))
    d = ImageDraw.Draw(img)
    d.ellipse([120, 240, 320, 440], fill=(40, 90, 220))    # left: blue
    d.rectangle([580, 240, 780, 440], fill=(220, 160, 30))  # right: orange
    img.save(IMG_DIR / "g05_spatial.png")
    return {"id": "g05_spatial", "task": "vqa_keyword", "image": "images/g05_spatial.png",
            "tags": ["spatial", "color"], "track": "synthetic", "answer": ["blue"],
            "meta": {"question": "What colour is the shape on the LEFT side of the image?"}}


def open_ended() -> dict:
    img = Image.new("RGB", (W, H), (135, 190, 240))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 430, W, H], fill=(90, 170, 90))          # grass
    d.ellipse([690, 60, 820, 190], fill=(255, 230, 90))      # sun
    # simple house
    d.rectangle([300, 300, 520, 460], fill=(200, 120, 90))
    d.polygon([(290, 300), (410, 200), (530, 300)], fill=(150, 60, 50))
    d.rectangle([380, 380, 440, 460], fill=(90, 60, 40))     # door
    img.save(IMG_DIR / "g06_scene.png")
    return {"id": "g06_scene", "task": "open_ended", "image": "images/g06_scene.png",
            "tags": ["caption"], "track": "synthetic",
            "answer": "A simple daytime outdoor scene: a house with a red/dark triangular "
                      "roof and a door, on green grass, under a blue sky with a yellow sun.",
            "meta": {"question": "Describe this image in one or two sentences."}}


def main() -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    items = [ocr_sign(), counting(), bar_chart(), table_lookup(), spatial_color(), open_ended()]
    manifest = {
        "name": "general-vlm",
        "description": "Small general VLM suite with exact answers + one judged caption.",
        "items": items,
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {len(items)} general items to {IMG_DIR} and manifest.json")


if __name__ == "__main__":
    main()
