"""Post-production overlay compositor.

Seedance renders the moving picture + native audio. Brand text that must be
exact — the logo, contact bar, ₹/number badges, and Hindi (Devanagari) captions —
is burned on afterwards here, because in-model text (especially Devanagari) is
unreliable. See DESIGN.md ("On-screen text — Hybrid").

Toolchain is fully pip-installable (no system ffmpeg/font needed):
  * Pillow (+raqm) renders each overlay to a transparent, full-frame PNG with
    proper Devanagari shaping using the bundled Noto Sans Devanagari font.
  * imageio-ffmpeg provides a static ffmpeg binary that composites the PNGs onto
    the video at their timestamps.

Self-test:  python overlays.py --selftest   (synthesizes a clip + burns overlays)
"""

import os
import subprocess
import tempfile
import uuid

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(HERE, "static", "fonts", "NotoSansDevanagari.ttf")
OUT_DIR = os.path.join(HERE, "static", "outputs")


def ffmpeg_exe():
    """Path to a working ffmpeg binary (bundled via imageio-ffmpeg, or $PATH)."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _font(size):
    return ImageFont.truetype(FONT_PATH, int(size))


def _sanitize(text):
    """Drop symbols/emoji the Devanagari font has no glyph for (they'd show as
    boxes). Keeps ₹, Latin, digits, punctuation and all Devanagari."""
    out = []
    for ch in text or "":
        o = ord(ch)
        emoji = (0x2600 <= o <= 0x27BF or 0x1F000 <= o <= 0x1FAFF
                 or o in (0xFE0F, 0x20E3) or 0x1F1E6 <= o <= 0x1F1FF)
        if not emoji:
            out.append(ch)
    return "".join(out).strip()


def preflight():
    """Return (ok, message). Verifies the font + ffmpeg are usable before we try."""
    if not os.path.isfile(FONT_PATH):
        return False, f"Devanagari font missing at {FONT_PATH}"
    try:
        _font(32)
    except Exception as e:
        return False, f"font not loadable: {e}"
    exe = ffmpeg_exe()
    try:
        subprocess.run([exe, "-version"], capture_output=True, check=True)
    except Exception as e:
        return False, ("ffmpeg not available — `pip install imageio-ffmpeg` "
                       f"(or install ffmpeg): {e}")
    return True, "ok"


# ── position anchors ─────────────────────────────────────────────────────────
def _anchor(position, W, H):
    """Map a named position to (x, y, halign, valign) for the text block."""
    m = int(W * 0.06)                       # side margin
    pos = (position or "bottom-bar").lower()
    top, mid, bot = int(H * 0.07), int(H * 0.5), int(H * 0.86)
    table = {
        "top-left": (m, top, "left", "top"),
        "top-center": (W // 2, top, "center", "top"),
        "top-right": (W - m, top, "right", "top"),
        "center": (W // 2, mid, "center", "middle"),
        "bottom-left": (m, bot, "left", "bottom"),
        "bottom-center": (W // 2, bot, "center", "bottom"),
        "bottom-bar": (W // 2, bot, "center", "bottom"),
        "bottom-right": (W - m, bot, "right", "bottom"),
    }
    return table.get(pos, table["bottom-bar"])


def _text_size(draw, text, font):
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0], b[3] - b[1], b[1]


def _draw_pill(draw, cx_or_x, y, text, font, halign, valign,
               fg=(255, 255, 255, 255), bg=(10, 17, 22, 200), pad=(26, 16), radius=18):
    """Draw text on a rounded translucent pill; return the pill bbox."""
    tw, th, off = _text_size(draw, text, font)
    px, py = pad
    bw, bh = tw + 2 * px, th + 2 * py
    x = cx_or_x
    if halign == "center":
        x0 = x - bw // 2
    elif halign == "right":
        x0 = x - bw
    else:
        x0 = x
    if valign == "middle":
        y0 = y - bh // 2
    elif valign == "bottom":
        y0 = y - bh
    else:
        y0 = y
    draw.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=radius, fill=bg)
    draw.text((x0 + px, y0 + py - off), text, font=font, fill=fg,
              features=["kern", "liga"])
    return (x0, y0, x0 + bw, y0 + bh)


def _render_png(W, H, kind, text, position, out_path, voffset=0, accent=(225, 29, 42)):
    """Render one full-frame transparent overlay PNG. `voffset` shifts the block
    vertically so concurrent items in the same band stack instead of overlapping."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    text = _sanitize(text)
    if not text:
        img.save(out_path)
        return out_path
    if kind == "caption":
        # bottom captions, larger, high-contrast bar
        font = _font(H * 0.038)
        _draw_pill(d, W // 2, int(H * 0.90) + voffset, text, font, "center", "bottom",
                   bg=(0, 0, 0, 190), pad=(30, 18), radius=14)
    elif kind == "badge":
        font = _font(H * 0.040)
        x, y, ha, va = _anchor(position, W, H)
        _draw_pill(d, x, y + voffset, text, font, ha, va,
                   bg=(accent[0], accent[1], accent[2], 235), pad=(26, 16), radius=22)
    else:  # generic overlay text
        font = _font(H * 0.034)
        x, y, ha, va = _anchor(position, W, H)
        _draw_pill(d, x, y + voffset, text, font, ha, va)
    img.save(out_path)
    return out_path


def _region(kind, position):
    if kind == "caption":
        return "bottom"
    p = (position or "bottom-bar").lower()
    if p.startswith("top"):
        return "top"
    if p.startswith("bottom"):
        return "bottom"
    return "mid"


def _assign_stack_levels(items):
    """Give each item a stacking level so time-overlapping items in the same band
    don't collide. Returns the same list with '_level' and '_region' set."""
    placed = {"top": [], "bottom": [], "mid": []}
    for it in items:
        ts, te = it.get("t_start"), it.get("t_end")
        win = (float(ts) if ts is not None else 0.0,
               float(te) if te is not None else 1e9)
        reg = _region(it.get("kind") or "overlay", it.get("position"))
        level = 0
        for (w2, lv) in placed[reg]:
            if win[0] < w2[1] and w2[0] < win[1]:      # time windows overlap
                level = max(level, lv + 1)
        placed[reg].append((win, level))
        it["_level"], it["_region"] = level, reg
    return items


def _fetch(url_or_path):
    """Return a local file path for a URL / data URI / local path."""
    if os.path.isfile(url_or_path):
        return url_or_path, False
    import base64
    import urllib.request
    tmp = os.path.join(tempfile.gettempdir(), "ovl_" + uuid.uuid4().hex)
    if url_or_path.startswith("data:"):
        header, b64 = url_or_path.split(",", 1)
        ext = ".mp4" if "video" in header else (".png" if "image" in header else ".bin")
        p = tmp + ext
        with open(p, "wb") as f:
            f.write(base64.b64decode(b64))
        return p, True
    p = tmp + os.path.splitext(url_or_path.split("?")[0])[1][:5]
    urllib.request.urlretrieve(url_or_path, p)
    return p, True


def compose(video_src, items, width=720, height=1280, logo_src=None, logo_scale=0.18):
    """
    Burn overlays onto a video.
      video_src : URL / data URI / local path of the source video
      items     : list of {kind: 'overlay'|'badge'|'caption', text, position,
                           t_start, t_end}
      logo_src  : optional image URL/path composited top-left for the whole clip
    Returns (result_dict, http_status). On success result has 'video_path' and
    'video_url' (served from static/outputs).
    """
    ok, msg = preflight()
    if not ok:
        return {"error": msg}, 500
    os.makedirs(OUT_DIR, exist_ok=True)
    W, H = int(width), int(height)

    try:
        video_path, vtmp = _fetch(video_src)
    except Exception as e:
        return {"error": f"could not fetch source video: {e}"}, 400

    tmpdir = tempfile.mkdtemp(prefix="ovl_")
    png_inputs, filters, chains = [], [], []
    label = "0:v"

    # logo (persistent)
    idx = 1
    if logo_src:
        try:
            logo_path, _ = _fetch(logo_src)
            lp = os.path.join(tmpdir, "logo.png")
            lim = Image.open(logo_path).convert("RGBA")
            lw = int(W * logo_scale)
            lh = int(lim.height * lw / lim.width)
            lim.resize((lw, lh)).save(lp)
            png_inputs.append(lp)
            m = int(W * 0.05)
            filters.append(f"[{label}][{idx}:v]overlay={m}:{m}[v{idx}]")
            label = f"v{idx}"
            idx += 1
        except Exception:
            pass  # logo is best-effort

    # timed overlays — assign stacking levels first so concurrent items don't collide
    rowH = int(H * 0.085)
    _assign_stack_levels([it for it in items if (it.get("text") or "").strip()])
    for it in items:
        text = (it.get("text") or "").strip()
        if not text:
            continue
        kind = it.get("kind") or "overlay"
        # top bands stack downward, bottom bands stack upward
        sign = 1 if it.get("_region") == "top" else -1
        voffset = sign * it.get("_level", 0) * rowH
        png = os.path.join(tmpdir, f"o{idx}.png")
        _render_png(W, H, kind, text, it.get("position"), png, voffset=voffset)
        png_inputs.append(png)
        ts, te = it.get("t_start"), it.get("t_end")
        enable = ""
        if ts is not None and te is not None and (float(te) > float(ts)):
            enable = f":enable='between(t,{float(ts)},{float(te)})'"
        filters.append(f"[{label}][{idx}:v]overlay=0:0{enable}[v{idx}]")
        label = f"v{idx}"
        idx += 1

    out_path = os.path.join(OUT_DIR, f"ad_{uuid.uuid4().hex[:10]}.mp4")
    cmd = [ffmpeg_exe(), "-y", "-i", video_path]
    for p in png_inputs:
        cmd += ["-i", p]

    if filters:
        cmd += ["-filter_complex", ";".join(filters), "-map", f"[{label}]"]
        # keep original audio if present
        cmd += ["-map", "0:a?", "-c:a", "copy"]
    else:
        cmd += ["-c", "copy"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.isfile(out_path):
            return {"error": "ffmpeg failed", "detail": r.stderr[-1200:]}, 500
    except Exception as e:
        return {"error": str(e)}, 500

    return {"video_path": out_path,
            "video_url": "/static/outputs/" + os.path.basename(out_path),
            "overlay_count": len(png_inputs)}, 200


def build_items_from_plan(plan, captions=True):
    """Turn an Ad Plan into overlay items: overlay_text entries as badges/text,
    plus optional Hindi captions from each scene's VO line."""
    items = []
    for o in (plan or {}).get("overlay_text", []) or []:
        txt = (o.get("text") or "")
        kind = "badge" if any(c.isdigit() for c in txt) or "₹" in txt else "overlay"
        items.append({"kind": kind, "text": txt, "position": o.get("position"),
                      "t_start": o.get("t_start"), "t_end": o.get("t_end")})
    if captions:
        for s in (plan or {}).get("scenes", []) or []:
            line = (s.get("vo_hindi") or "").strip()
            if line:
                items.append({"kind": "caption", "text": line,
                              "t_start": s.get("t_start"), "t_end": s.get("t_end")})
    return items


def _selftest():
    """Synthesize a 6s test clip and burn a representative overlay set."""
    ok, msg = preflight()
    print("preflight:", ok, msg)
    if not ok:
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    src = os.path.join(tempfile.gettempdir(), "selftest_src.mp4")
    subprocess.run([ffmpeg_exe(), "-y", "-f", "lavfi", "-i",
                    "gradients=s=720x1280:d=6", "-t", "6", "-pix_fmt", "yuv420p", src],
                   capture_output=True, check=True)
    items = [
        {"kind": "badge", "text": "₹2.45 लाख", "position": "top-center", "t_start": 0, "t_end": 6},
        {"kind": "badge", "text": "7-साल वारंटी", "position": "top-right", "t_start": 1, "t_end": 6},
        {"kind": "caption", "text": "गैलेक्सी होंडा — अभी बुक करें", "t_start": 0, "t_end": 3},
        {"kind": "caption", "text": "StrideOne AeroRush ₹4,999", "t_start": 3, "t_end": 6},
        {"kind": "overlay", "text": "☎ 1800-123-456", "position": "bottom-left", "t_start": 4, "t_end": 6},
    ]
    res, status = compose(src, items, 720, 1280)
    print("result:", status, res)


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        _selftest()
    else:
        print("usage: python overlays.py --selftest")
