#!/usr/bin/env python3
"""CLI: run the VLM eval over a dataset and write an HTML report.

Examples
--------
    # Both datasets, both providers, 3 repeats -> results/report.html
    python run_eval.py --dataset all --repeats 3

    # Only the 3D-director track
    python run_eval.py --dataset director3d

    # Offline pipeline smoke-test with a scripted mock provider (no keys/network)
    python run_eval.py --dataset all --mock
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vlm_eval.config import all_providers, judge_provider_name
from vlm_eval.providers import ChatClient
from vlm_eval.report import write_report
from vlm_eval.runner import load_dataset, run

ROOT = Path(__file__).resolve().parent
DATASETS = {
    "director3d": ROOT / "datasets/director3d/manifest.json",
    "general": ROOT / "datasets/general/manifest.json",
}


def resolve_manifests(name: str) -> list[Path]:
    if name == "all":
        return [p for p in DATASETS.values() if p.exists()]
    if name in DATASETS:
        return [DATASETS[name]]
    p = Path(name)
    if p.exists():
        return [p]
    sys.exit(f"Unknown dataset '{name}'. Use: director3d | general | all | <manifest.json path>")


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed vs Gemini VLM eval")
    ap.add_argument("--dataset", default="all", help="director3d | general | all | path")
    ap.add_argument("--providers", default="seed,gemini", help="comma list: seed,gemini")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", default=str(ROOT / "results/report.html"))
    ap.add_argument("--mock", action="store_true", help="use scripted mock clients (no network)")
    args = ap.parse_args()

    want = [p.strip() for p in args.providers.split(",") if p.strip()]
    provider_cfgs = {k: v for k, v in all_providers().items() if k in want}
    if not provider_cfgs:
        sys.exit(f"No known providers in {want!r}")

    items = []
    for man in resolve_manifests(args.dataset):
        items.extend(load_dataset(man))
    print(f"Loaded {len(items)} items across {len(provider_cfgs)} providers × {args.repeats} repeats")

    clients = None
    judge = None
    if args.mock:
        from tests.mock_client import MockClient
        clients = {name: MockClient(cfg) for name, cfg in provider_cfgs.items()}
        judge = MockClient(next(iter(provider_cfgs.values())))
    else:
        missing = [k for k, c in provider_cfgs.items() if not c.configured]
        if missing:
            sys.exit(
                f"Missing API config for: {missing}. Copy .env.example to .env and fill keys, "
                f"or pass --mock for an offline pipeline test."
            )
        jname = judge_provider_name()
        if jname in provider_cfgs:
            judge = ChatClient(provider_cfgs[jname])

    results = run(provider_cfgs, items, repeats=args.repeats,
                  judge_client=judge, clients=clients,
                  progress=lambda m: print("  ·", m))

    out = write_report(results, args.out)
    json_out = Path(args.out).with_suffix(".json")
    json_out.write_text(json.dumps(results, indent=2))
    print(f"\nReport:  {out}\nJSON:    {json_out}")
    lb = results["leaderboard"]
    if lb:
        print("\nLeaderboard:")
        for i, r in enumerate(lb):
            print(f"  {i+1}. {r['label']:<32} composite={r['composite']:.2f} "
                  f"json={round(r['json_rate']*100)}% lat={r['lat_med']:.1f}s")


if __name__ == "__main__":
    main()
