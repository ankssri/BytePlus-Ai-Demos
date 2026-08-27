"""Batch eval runner: runs providers over a dataset and aggregates results."""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Callable, Optional

from .config import ProviderConfig, judge_provider_name
from .providers import ChatClient
from .tasks import EvalItem, ItemScore, get_task

# Sub-metric columns surfaced for the director3d task, in report order.
DIRECTOR_METRICS = ["det_f1", "iou", "roll", "facing", "leftright", "depth", "light"]


def load_dataset(manifest_path: str | Path) -> list[EvalItem]:
    manifest_path = Path(manifest_path)
    data = json.loads(manifest_path.read_text())
    base = manifest_path.parent
    return [EvalItem.from_dict(d, base) for d in data["items"]]


def _pct(n: int, d: int) -> float:
    return (n / d) if d else 0.0


def run(
    providers: dict[str, ProviderConfig],
    items: list[EvalItem],
    repeats: int = 3,
    judge_client: Optional[ChatClient] = None,
    progress: Optional[Callable[[str], None]] = None,
    clients: Optional[dict] = None,
) -> dict:
    """Execute the eval and return an aggregated results dict.

    ``clients`` may be supplied to inject custom/mock clients (keyed by provider
    name); otherwise a real :class:`ChatClient` is built per provider config.
    """
    clients = clients or {name: ChatClient(cfg) for name, cfg in providers.items()}
    labels = {name: cfg.label for name, cfg in providers.items()}

    def log(msg: str) -> None:
        if progress:
            progress(msg)

    # raw[provider][item_id] = list[ItemScore] across repeats
    raw: dict[str, dict[str, list[ItemScore]]] = {p: {} for p in providers}

    for item in items:
        task = get_task(item.task)
        for pname, client in clients.items():
            scores: list[ItemScore] = []
            for r in range(repeats):
                log(f"{pname} · {item.id} · repeat {r + 1}/{repeats}")
                score = task.run(client, item, judge=judge_client)
                scores.append(score)
            raw[pname][item.id] = scores

    return aggregate(raw, items, providers, labels, repeats)


def aggregate(raw, items, providers, labels, repeats) -> dict:
    item_by_id = {it.id: it for it in items}
    provider_names = list(providers.keys())

    leaderboard = []
    reliability = {}
    tracks = {}
    capabilities: dict[str, dict[str, list[float]]] = {}

    for p in provider_names:
        all_scores = [s for sid in raw[p] for s in raw[p][sid]]
        scored = [s for s in all_scores if s.composite is not None]
        valid = [s for s in all_scores if s.valid]
        latencies = [s.latency_s for s in all_scores if s.latency_s and s.valid]

        composite = statistics.mean([s.composite for s in scored]) if scored else 0.0
        json_rate = _pct(len(valid), len(all_scores))
        lat_med = statistics.median(latencies) if latencies else 0.0
        lat_max = max(latencies) if latencies else 0.0

        # Per-director-metric means across scored calls.
        metric_means = {}
        for mk in DIRECTOR_METRICS:
            vals = [s.metrics.get(mk) for s in scored if s.metrics.get(mk) is not None]
            metric_means[mk] = statistics.mean(vals) if vals else None

        # Score jitter: mean stddev of composite across repeats per item.
        jitters = []
        for sid in raw[p]:
            comps = [s.composite for s in raw[p][sid] if s.composite is not None]
            if len(comps) >= 2:
                jitters.append(statistics.pstdev(comps))
        score_jitter = statistics.mean(jitters) if jitters else 0.0

        leaderboard.append({
            "provider": p, "label": labels[p], "composite": composite,
            "metrics": metric_means, "json_rate": json_rate,
            "lat_med": lat_med, "lat_max": lat_max,
        })
        reliability[p] = {
            "json_rate": json_rate, "lat_med": lat_med, "lat_max": lat_max,
            "score_jitter": score_jitter, "n_calls": len(all_scores), "n_valid": len(valid),
        }

        # Track breakdown.
        tr: dict[str, list[float]] = {}
        for sid in raw[p]:
            track = item_by_id[sid].track
            for s in raw[p][sid]:
                if s.composite is not None:
                    tr.setdefault(track, []).append(s.composite)
        tracks[p] = {k: statistics.mean(v) for k, v in tr.items()}

        # Capability breakdown.
        for sid in raw[p]:
            for tag in item_by_id[sid].tags:
                bucket = capabilities.setdefault(tag, {})
                for s in raw[p][sid]:
                    if s.composite is not None:
                        bucket.setdefault(p, []).append(s.composite)

    leaderboard.sort(key=lambda x: x["composite"], reverse=True)

    cap_out = {
        tag: {p: (statistics.mean(v) if v else None) for p, v in provs.items()}
        for tag, provs in capabilities.items()
    }

    # Per-item summary with chips.
    item_rows = []
    for it in items:
        row = {"id": it.id, "task": it.task, "tags": it.tags, "track": it.track,
               "image": it.image, "image_abs": it.image_path, "providers": {}}
        for p in provider_names:
            scores = raw[p][it.id]
            row["providers"][p] = _summarize_item(scores, repeats)
        item_rows.append(row)

    # Which metric columns actually have data (director3d present).
    metric_keys = [mk for mk in DIRECTOR_METRICS
                   if any(lb["metrics"].get(mk) is not None for lb in leaderboard)]

    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "repeats": repeats,
        "providers": provider_names,
        "provider_labels": labels,
        "leaderboard": leaderboard,
        "tracks": tracks,
        "capabilities": cap_out,
        "reliability": reliability,
        "items": item_rows,
        "metric_keys": metric_keys,
    }


def _summarize_item(scores: list[ItemScore], repeats: int) -> dict:
    """Collapse a provider's repeats on one item into a status + chips."""
    n_invalid = sum(1 for s in scores if not s.valid)
    scored = [s for s in scores if s.composite is not None]
    composite = statistics.mean([s.composite for s in scored]) if scored else None

    chips: list[str] = []
    if n_invalid:
        chips.append(f"invalid/empty {n_invalid}/{repeats}×")
    # Aggregate error notes across repeats (unique, order-preserving).
    seen = set()
    for s in scores:
        for note in s.notes:
            if note and note not in seen and note != "invalid/empty JSON":
                seen.add(note)
                chips.append(note)

    if composite is not None and composite >= 0.999 and not chips:
        status = "correct"
    elif composite is None:
        status = "failed"
    else:
        status = "partial"

    return {
        "status": status,
        "composite": composite,
        "chips": chips,
        "n_invalid": n_invalid,
        "lat_max": max((s.latency_s for s in scores if s.latency_s), default=0.0),
    }
