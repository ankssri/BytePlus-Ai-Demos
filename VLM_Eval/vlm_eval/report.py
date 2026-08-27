"""Render a self-contained HTML report from an aggregated results dict."""
from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from .utils import image_to_data_url

METRIC_LABELS = {
    "det_f1": "det F1", "iou": "IoU", "roll": "roll", "facing": "facing",
    "leftright": "L→R", "depth": "depth", "light": "light",
}


def _fmt(v, digits=2):
    if v is None:
        return "—"
    return f"{v:.{digits}f}"


def _pct(v):
    return "—" if v is None else f"{round(v * 100)}%"


def _thumb(path: str, max_kb: int = 400) -> str:
    try:
        p = Path(path)
        if not p.exists():
            return ""
        return image_to_data_url(p)
    except Exception:
        return ""


def _tldr(results: dict) -> str:
    lb = results["leaderboard"]
    if not lb:
        return ""
    lines = []
    winner = lb[0]
    lines.append(
        f"<b>{html.escape(winner['label'])}</b> leads with composite "
        f"<b>{_fmt(winner['composite'])}</b> ({_pct(winner['json_rate'])} valid JSON, "
        f"median {_fmt(winner['lat_med'])}s)."
    )
    for row in lb[1:]:
        gap = winner["composite"] - row["composite"]
        rel = f"{_fmt(row['composite'])}"
        note = ""
        if row["json_rate"] < 0.9:
            note = (f" — but only {_pct(row['json_rate'])} of calls returned valid JSON "
                    f"(reliability, not raw capability, is the gap)")
        lines.append(
            f"<b>{html.escape(row['label'])}</b> at {rel} (Δ {_fmt(gap)}){note}."
        )
    return "<br>".join(lines)


def _leaderboard_table(results: dict) -> str:
    mk = results["metric_keys"]
    head = "".join(f"<th>{METRIC_LABELS.get(k, k)}</th>" for k in mk)
    rows = []
    for i, row in enumerate(results["leaderboard"]):
        metric_cells = "".join(f"<td>{_fmt(row['metrics'].get(k))}</td>" for k in mk)
        cls = "win" if i == 0 else ""
        rows.append(
            f"<tr class='{cls}'>"
            f"<td class='rank'>{i + 1}</td>"
            f"<td class='prov'>{html.escape(row['label'])}</td>"
            f"<td class='big'>{_fmt(row['composite'])}</td>"
            f"{metric_cells}"
            f"<td>{_pct(row['json_rate'])}</td>"
            f"<td>{_fmt(row['lat_med'])}/{_fmt(row['lat_max'])}s</td>"
            f"</tr>"
        )
    return (
        "<table><thead><tr><th>#</th><th>Provider</th><th>Composite</th>"
        f"{head}<th>JSON</th><th>lat med/max</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _tracks_table(results: dict) -> str:
    provs = results["providers"]
    all_tracks = sorted({t for p in provs for t in results["tracks"].get(p, {})})
    if not all_tracks:
        return "<p class='muted'>No track data.</p>"
    head = "".join(f"<th>{html.escape(t)}</th>" for t in all_tracks)
    rows = []
    for p in provs:
        cells = "".join(f"<td>{_fmt(results['tracks'].get(p, {}).get(t))}</td>" for t in all_tracks)
        rows.append(f"<tr><td class='prov'>{html.escape(results['provider_labels'][p])}</td>{cells}</tr>")
    return f"<table><thead><tr><th>Provider</th>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _capabilities_table(results: dict) -> str:
    provs = results["providers"]
    caps = results["capabilities"]
    if not caps:
        return "<p class='muted'>No capability tags.</p>"
    head = "".join(f"<th>{html.escape(results['provider_labels'][p])}</th>" for p in provs)
    rows = []
    for tag in sorted(caps):
        cells = ""
        best = max((caps[tag].get(p) or -1) for p in provs)
        for p in provs:
            v = caps[tag].get(p)
            cls = "hi" if v is not None and v == best and best >= 0 else ""
            cells += f"<td class='{cls}'>{_fmt(v)}</td>"
        rows.append(f"<tr><td class='cap'>{html.escape(tag)}</td>{cells}</tr>")
    return f"<table><thead><tr><th>Capability</th>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _reliability_table(results: dict) -> str:
    provs = results["providers"]
    rows = []
    for p in provs:
        r = results["reliability"][p]
        rows.append(
            f"<tr><td class='prov'>{html.escape(results['provider_labels'][p])}</td>"
            f"<td>{_pct(r['json_rate'])}</td>"
            f"<td>{r['n_valid']}/{r['n_calls']}</td>"
            f"<td>{_fmt(r['score_jitter'])}</td>"
            f"<td>{_fmt(r['lat_med'])}s</td>"
            f"<td>{_fmt(r['lat_max'])}s</td></tr>"
        )
    return (
        "<table><thead><tr><th>Provider</th><th>JSON valid</th><th>valid/total</th>"
        "<th>score jitter</th><th>lat median</th><th>lat max</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _chip(text: str, kind: str) -> str:
    return f"<span class='chip {kind}'>{html.escape(text)}</span>"


def _item_cards(results: dict, track: str) -> str:
    provs = results["providers"]
    cards = []
    for it in results["items"]:
        if it["track"] != track:
            continue
        thumb = _thumb(it.get("image_abs", ""))
        img_html = f"<img src='{thumb}' alt='{html.escape(it['id'])}'>" if thumb else ""
        tags = " ".join(f"<span class='tag'>{html.escape(t)}</span>" for t in it["tags"])
        prov_blocks = []
        for p in provs:
            s = it["providers"][p]
            status = s["status"]
            if status == "correct":
                chips = _chip("✓ correct", "ok")
            elif status == "failed":
                chips = _chip("no valid output", "bad")
            else:
                chips = "".join(
                    _chip(c, "bad" if "invalid" in c or "missed" in c or "phantom" in c
                          or "wrong" in c or "off" in c else "warn")
                    for c in s["chips"]
                ) or _chip(f"score {_fmt(s['composite'])}", "warn")
            comp = _fmt(s["composite"]) if s["composite"] is not None else "—"
            prov_blocks.append(
                f"<div class='pv'><div class='pvh'>{html.escape(results['provider_labels'][p])}"
                f"<span class='sc'>{comp}</span></div><div class='chips'>{chips}</div></div>"
            )
        cards.append(
            f"<div class='card'><div class='thumb'>{img_html}</div>"
            f"<div class='meta'><div class='cid'>{html.escape(it['id'])}</div>"
            f"<div class='tags'>{tags}</div>{''.join(prov_blocks)}</div></div>"
        )
    return f"<div class='cards'>{''.join(cards)}</div>" if cards else ""


def render(results: dict) -> str:
    tldr = _tldr(results)
    has_real = any(it["track"] == "real" for it in results["items"])
    real_section = ""
    if has_real:
        real_section = (
            "<h2>05 · Test cases — real / hand-labeled</h2>"
            + _item_cards(results, "real")
        )
    synthetic_cards = _item_cards(results, "synthetic")

    data_json = html.escape(json.dumps(results, indent=2))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Seed vs Gemini — VLM Eval</title>
<style>
:root {{
  --bg:#0e1116; --panel:#161b22; --line:#232a34; --fg:#e6edf3; --muted:#8b949e;
  --win:#1f6feb; --ok:#2ea043; --warn:#9e6a03; --bad:#da3633; --hi:#132a1a;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
.wrap {{ max-width:1100px; margin:0 auto; padding:32px 20px 80px; }}
h1 {{ font-size:26px; margin:0 0 4px; }}
h2 {{ font-size:18px; margin:38px 0 12px; color:#c9d1d9; }}
.sub {{ color:var(--muted); margin:0 0 22px; }}
.tldr {{ background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--win);
  border-radius:8px; padding:16px 18px; margin:0 0 8px; }}
table {{ width:100%; border-collapse:collapse; background:var(--panel);
  border:1px solid var(--line); border-radius:8px; overflow:hidden; font-size:14px; }}
th,td {{ padding:9px 12px; text-align:center; border-bottom:1px solid var(--line); }}
th {{ background:#1b2029; color:var(--muted); font-weight:600; }}
td.prov,td.cap,th:first-child {{ text-align:left; }}
td.rank {{ color:var(--muted); }}
td.big {{ font-weight:700; font-size:16px; }}
tr.win td {{ background:rgba(31,111,235,.10); }}
td.hi {{ background:var(--hi); color:#3fb950; font-weight:600; }}
.muted {{ color:var(--muted); }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:14px; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:10px;
  overflow:hidden; display:flex; flex-direction:column; }}
.thumb {{ background:#0b0e13; aspect-ratio:4/3; display:flex; align-items:center; justify-content:center; }}
.thumb img {{ max-width:100%; max-height:100%; object-fit:contain; }}
.meta {{ padding:12px 14px; }}
.cid {{ font-weight:600; font-size:14px; }}
.tags {{ margin:6px 0 10px; }}
.tag {{ display:inline-block; font-size:11px; color:var(--muted); border:1px solid var(--line);
  border-radius:20px; padding:1px 8px; margin:0 4px 4px 0; }}
.pv {{ border-top:1px solid var(--line); padding:8px 0 2px; }}
.pvh {{ display:flex; justify-content:space-between; font-size:13px; color:#c9d1d9; }}
.sc {{ color:var(--muted); }}
.chips {{ margin:5px 0 2px; }}
.chip {{ display:inline-block; font-size:11px; border-radius:5px; padding:2px 7px; margin:0 4px 4px 0; }}
.chip.ok {{ background:rgba(46,160,67,.16); color:#3fb950; }}
.chip.warn {{ background:rgba(158,106,3,.18); color:#d29922; }}
.chip.bad {{ background:rgba(218,54,51,.16); color:#f85149; }}
details {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:10px 14px; margin-top:14px; }}
pre {{ overflow:auto; font-size:12px; color:var(--muted); }}
.foot {{ color:var(--muted); font-size:13px; margin-top:34px; border-top:1px solid var(--line); padding-top:16px; }}
</style></head>
<body><div class="wrap">
<h1>Seed 2.1 vs Gemini 3.1 — VLM Evaluation</h1>
<p class="sub">Generated {results['generated_at']} · {results['repeats']} repeats/call ·
rule-based scoring where ground truth is exact · reliability measured per call.</p>

<div class="tldr">{tldr}</div>

<h2>01 · Overall leaderboard <span class="muted">(composite = mean of sub-metrics)</span></h2>
{_leaderboard_table(results)}

<h2>02 · By track <span class="muted">(synthetic = exact GT · real = hand-labeled)</span></h2>
{_tracks_table(results)}

<h2>03 · By capability <span class="muted">(composite on images carrying each tag)</span></h2>
{_capabilities_table(results)}

<h2>04 · Reliability &amp; determinism</h2>
{_reliability_table(results)}

<h2>05 · Test cases — synthetic (exact GT) <span class="muted">chips flag each model's errors</span></h2>
{synthetic_cards}
{real_section}

<details><summary>Raw results JSON</summary><pre>{data_json}</pre></details>

<div class="foot">
Composite is the equal-weight mean of the available sub-metrics. det F1 / IoU match predicted
boxes to ground truth at IoU ≥ 0.5. roll = orientation quadrant. L→R / depth = pairwise ordering
vs GT via matched boxes. light = key-light direction shares a component with GT. JSON = fraction of
calls returning a parseable object. Synthetic scenes isolate spatial reasoning with exact ground
truth; add real photos with hand labels to the manifest for ecological validity.
</div>
</div></body></html>"""


def write_report(results: dict, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(results), encoding="utf-8")
    return out_path
