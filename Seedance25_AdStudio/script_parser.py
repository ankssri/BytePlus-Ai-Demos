"""
script_parser.py — Turn the ad markdown files into structured, per-shot data.

Two inputs (both optional, but at least one required):
  script_md     — the "script" file: a Voiceover table + a Shot-by-shot table
  keyframes_md  — the "keyframes" file: per-keyframe Image prompt + Seedance motion prompt

The parser is tolerant of the sample format shipped in sample_scripts/ but tries
hard not to crash on small deviations. Output is a dict:

{
  "title": str,
  "presenter": str,                 # canonical presenter description (for [PRESENTER] substitution)
  "voiceover": [ {num, t_start, t_end, hindi, roman, english} ],
  "shots": [
     {
       "kf": "A1",
       "time": 0.6,
       "camera": "...",
       "action": "...",
       "setting": "...",
       "graphic": "...",
       "title": "Open / presenter outside dealership",
       "image_prompt": "...",       # [PRESENTER] already substituted
       "overlay": "...",
       "motion_prompt": "...",
       "dialogue_hindi": "...",     # matched by time window (may be "")
       "dialogue_english": "...",
       "dialogue_roman": "...",
     }, ...
  ],
  "warnings": [str, ...],
}
"""

import re

# Any dash used in time ranges: hyphen, en-dash, em-dash.
_DASH = r"[-–—]"


def _to_float(s):
    try:
        return float(re.sub(r"[^0-9.]", "", s))
    except (ValueError, TypeError):
        return None


def _split_table_row(line):
    """Split a markdown table row '| a | b | c |' into ['a','b','c']."""
    line = line.strip()
    if not line.startswith("|"):
        return None
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def _is_separator_row(cells):
    return all(re.fullmatch(r":?-{2,}:?", c or "") for c in cells if c != "")


def _find_tables(md):
    """Yield (header_cells, [row_cells,...]) for every markdown table in md."""
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        cells = _split_table_row(lines[i])
        # A header row is a table row immediately followed by a separator row.
        if cells and i + 1 < len(lines):
            sep = _split_table_row(lines[i + 1])
            if sep and _is_separator_row(sep):
                header = cells
                rows = []
                j = i + 2
                while j < len(lines):
                    r = _split_table_row(lines[j])
                    if not r or _is_separator_row(r):
                        break
                    rows.append(r)
                    j += 1
                yield header, rows
                i = j
                continue
        i += 1


def _header_index(header, *keywords):
    """Return the index of the first header cell containing any keyword (case-insensitive)."""
    for idx, h in enumerate(header):
        hl = (h or "").lower()
        if any(k in hl for k in keywords):
            return idx
    return None


def parse_voiceover(script_md):
    """Extract the voiceover / dialogue table."""
    vo = []
    for header, rows in _find_tables(script_md):
        i_num = _header_index(header, "#")
        i_time = _header_index(header, "time")
        i_hindi = _header_index(header, "hindi", "devanagari")
        i_roman = _header_index(header, "roman")
        i_eng = _header_index(header, "english")
        # A voiceover table must have a Hindi column and a Time column.
        if i_hindi is None or i_time is None:
            continue
        for r in rows:
            def cell(idx):
                return r[idx].strip() if idx is not None and idx < len(r) else ""
            time_raw = cell(i_time)
            m = re.search(rf"([0-9.]+)\s*{_DASH}\s*([0-9.]+)", time_raw)
            t_start = _to_float(m.group(1)) if m else _to_float(time_raw)
            t_end = _to_float(m.group(2)) if m else t_start
            vo.append({
                "num": cell(i_num),
                "t_start": t_start,
                "t_end": t_end,
                "hindi": cell(i_hindi),
                "roman": cell(i_roman),
                "english": cell(i_eng),
            })
        if vo:
            break
    return vo


def parse_shots(script_md):
    """Extract the shot-by-shot table (KF, time, camera, action, setting, graphic)."""
    shots = []
    for header, rows in _find_tables(script_md):
        i_kf = _header_index(header, "kf", "keyframe")
        if i_kf is None:
            continue
        i_time = _header_index(header, "time")
        i_cam = _header_index(header, "camera", "shot")
        i_act = _header_index(header, "action", "subject")
        i_set = _header_index(header, "setting")
        i_gfx = _header_index(header, "graphic", "overlay", "on-screen")
        for r in rows:
            def cell(idx):
                return r[idx].strip() if idx is not None and idx < len(r) else ""
            kf = cell(i_kf)
            if not kf:
                continue
            shots.append({
                "kf": kf,
                "time": _to_float(cell(i_time)),
                "camera": cell(i_cam),
                "action": cell(i_act),
                "setting": cell(i_set),
                "graphic": cell(i_gfx),
            })
        if shots:
            break
    return shots


def _parse_blockquote_after(md, anchor_idx):
    """Given the character index just after a '**Label:**' marker, collect the
    following markdown blockquote ('> ...' lines) as a single string."""
    tail = md[anchor_idx:]
    lines = tail.splitlines()
    out = []
    started = False
    for ln in lines:
        s = ln.strip()
        if s.startswith(">"):
            started = True
            out.append(s.lstrip(">").strip())
        elif started and s == "":
            # allow a single blank line inside a quote? Stop on blank to be safe.
            break
        elif started:
            break
        elif s == "":
            continue
        else:
            # Non-quote content before any quote line -> stop.
            if not started:
                break
    return " ".join(x for x in out if x).strip()


def parse_presenter(keyframes_md):
    """Pull the canonical PRESENTER description block."""
    if not keyframes_md:
        return ""
    m = re.search(r"\*\*PRESENTER[^\n]*\*\*", keyframes_md)
    if not m:
        return ""
    return _parse_blockquote_after(keyframes_md, m.end())


def parse_keyframes(keyframes_md, presenter=""):
    """Parse per-keyframe sections into {kf: {title, image_prompt, overlay, motion_prompt}}."""
    result = {}
    if not keyframes_md:
        return result
    # Section headers like: '## A1 — Open / presenter outside dealership (0.6 s)'
    # or '## B3 — ...'. Capture KF id + human title.
    section_re = re.compile(
        r"^#{2,3}\s*([A-Za-z]?\d+)\s*[–—-]?\s*(.*)$", re.MULTILINE)
    matches = list(section_re.finditer(keyframes_md))
    for idx, m in enumerate(matches):
        kf = m.group(1).strip()
        title = re.sub(r"\s*\([^)]*\)\s*$", "", m.group(2)).strip()
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(keyframes_md)
        block = keyframes_md[start:end]

        def grab(*labels):
            alts = "|".join(labels)
            lm = re.search(rf"\*\*(?:{alts})[^\n]*?\*\*", block)
            if not lm:
                return ""
            return _parse_blockquote_after(block, lm.end())

        image_prompt = grab("Image prompt")
        motion_prompt = grab(r"Seedance 2\.5 motion", "Seedance motion", "Motion")
        # End-card / graphic shots describe themselves under a **Note:** block.
        if not image_prompt:
            image_prompt = grab("Note")
        # Overlay is a single-line bold label, not a blockquote.
        om = re.search(r"\*\*Overlay:\*\*\s*(.+)", block)
        overlay = om.group(1).strip() if om else ""

        if presenter and image_prompt:
            image_prompt = image_prompt.replace("[PRESENTER]", presenter)
        result[kf] = {
            "title": title,
            "image_prompt": image_prompt,
            "overlay": overlay,
            "motion_prompt": motion_prompt,
        }
    return result


def _match_dialogue(shot_time, vo):
    """Find the voiceover line spoken during shot_time (or nearest by midpoint)."""
    if shot_time is None or not vo:
        return None
    # 1) Containing window.
    for v in vo:
        if v["t_start"] is not None and v["t_end"] is not None:
            if v["t_start"] <= shot_time <= v["t_end"]:
                return v
    # 2) Nearest by midpoint.
    best, best_d = None, None
    for v in vo:
        if v["t_start"] is None:
            continue
        mid = (v["t_start"] + (v["t_end"] if v["t_end"] is not None else v["t_start"])) / 2
        d = abs(mid - shot_time)
        if best_d is None or d < best_d:
            best, best_d = v, d
    return best


def _extract_title(md):
    if not md:
        return ""
    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    return m.group(1).strip() if m else ""


def parse(script_md="", keyframes_md=""):
    """Main entry: merge the two markdown files into per-shot data."""
    script_md = script_md or ""
    keyframes_md = keyframes_md or ""
    warnings = []

    presenter = parse_presenter(keyframes_md)
    vo = parse_voiceover(script_md)
    shots_meta = parse_shots(script_md)
    kf_prompts = parse_keyframes(keyframes_md, presenter)

    if not vo:
        warnings.append("No voiceover/dialogue table found in the script file.")
    if not shots_meta and not kf_prompts:
        warnings.append("No shots found in either file.")

    # Determine the ordered list of keyframe ids.
    if shots_meta:
        kf_order = [s["kf"] for s in shots_meta]
    else:
        kf_order = list(kf_prompts.keys())

    shots = []
    for s in ([{"kf": k} for k in kf_order] if not shots_meta else shots_meta):
        kf = s["kf"]
        kp = kf_prompts.get(kf, {})
        dlg = _match_dialogue(s.get("time"), vo)
        shot = {
            "kf": kf,
            "time": s.get("time"),
            "camera": s.get("camera", ""),
            "action": s.get("action", ""),
            "setting": s.get("setting", ""),
            "graphic": s.get("graphic", "") or kp.get("overlay", ""),
            "title": kp.get("title", ""),
            "image_prompt": kp.get("image_prompt", ""),
            "overlay": kp.get("overlay", "") or s.get("graphic", ""),
            "motion_prompt": kp.get("motion_prompt", ""),
            "dialogue_hindi": dlg["hindi"] if dlg else "",
            "dialogue_english": dlg["english"] if dlg else "",
            "dialogue_roman": dlg["roman"] if dlg else "",
        }
        # A shot with no image prompt is treated as a designed graphic card
        # (e.g. the outro contact card) to be built in post, not via Seedream.
        title_l = (shot["title"] or "").lower()
        shot["is_graphic"] = (not shot["image_prompt"]) or any(
            w in title_l for w in ("end card", "outro", "contact card"))
        if not shot["image_prompt"] and not shot["is_graphic"]:
            warnings.append(f"{kf}: no image prompt found in the keyframe file.")
        shots.append(shot)

    return {
        "title": _extract_title(script_md) or _extract_title(keyframes_md),
        "presenter": presenter,
        "voiceover": vo,
        "shots": shots,
        "warnings": warnings,
    }
