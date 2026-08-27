"""Scripted mock client for offline pipeline tests / demo reports.

It reads the scene id from the image filename, looks up ground truth from the
dataset manifests, and returns believable answers WITHOUT any network:

  * gemini  -> near-perfect (GT with small box jitter, correct labels, valid JSON)
  * seed    -> mostly correct but deliberately returns invalid JSON on a fraction
               of calls, reproducing the customer's observed reliability gap.

This is ONLY for demonstrating the harness end-to-end. Real evaluation uses the
HTTP :class:`ChatClient` with your API keys.
"""
from __future__ import annotations

import json
from pathlib import Path

from vlm_eval.config import ProviderConfig
from vlm_eval.providers import ChatResult

ROOT = Path(__file__).resolve().parent.parent


def _load_gt_index() -> dict:
    idx = {}
    for man in (ROOT / "datasets/director3d/manifest.json",
                ROOT / "datasets/general/manifest.json"):
        if man.exists():
            data = json.loads(man.read_text())
            for it in data["items"]:
                idx[Path(it["image"]).name] = it
    return idx


class MockClient:
    _GT = None

    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self.calls = 0
        if MockClient._GT is None:
            MockClient._GT = _load_gt_index()

    def _item_for(self, image_paths):
        if not image_paths:
            return None
        return MockClient._GT.get(Path(image_paths[0]).name)

    def chat(self, prompt, image_paths=None, *, system=None, expect_json=False,
             json_object=False, max_tokens=2048, temperature=None, extra_body=None) -> ChatResult:
        self.calls += 1
        latency = 5.5 if self.cfg.name == "gemini" else 6.5

        # Judge call (grading prompt) -> return a top score.
        if "grading" in prompt.lower() or prompt.strip().startswith("You are grading"):
            return ChatResult(self.cfg.name, self.cfg.model,
                              '{"score": 5, "reason": "faithful and complete"}',
                              latency, ok=True, json_obj={"score": 5, "reason": "ok"},
                              json_valid=True)

        item = self._item_for(image_paths)
        if item is None:
            return ChatResult(self.cfg.name, self.cfg.model, "unknown", latency, ok=True)

        task = item["task"]
        if task == "director3d":
            return self._director(item, latency)
        return self._general(item, task, latency)

    # -- director3d --------------------------------------------------------
    def _director(self, item, latency) -> ChatResult:
        # Seed: simulate ~40% invalid-JSON reliability gap + big stall latency.
        if self.cfg.name == "seed" and (self.calls % 5 in (0, 2)):
            return ChatResult(self.cfg.name, self.cfg.model,
                              "I need to think about this scene...", 28.0 + latency,
                              ok=True, json_valid=False, error="invalid/empty JSON")
        gt = item["ground_truth"]
        jitter = 4 if self.cfg.name == "gemini" else 16
        people = []
        for i, p in enumerate(gt["people"]):
            b = p["box"]
            d = jitter if (i + self.calls) % 2 == 0 else -jitter
            people.append({
                "box": [b[0] + d, b[1] + d, b[2] - d, b[3] - d],
                "orientation": p["orientation"],
                "facing": p["facing"] if self.cfg.name == "gemini" or i == 0 else p["facing"],
                "depth_rank": p["depth_rank"],
            })
        # Seed occasionally gets the light wrong.
        light = gt["light_direction"]
        if self.cfg.name == "seed" and self.calls % 3 == 0:
            light = "front"
        obj = {"people": people, "light_direction": light}
        text = json.dumps(obj)
        return ChatResult(self.cfg.name, self.cfg.model, text, latency,
                          ok=True, json_obj=obj, json_valid=True)

    # -- general -----------------------------------------------------------
    def _general(self, item, task, latency) -> ChatResult:
        ans = item.get("answer")
        if task == "vqa_numeric":
            # Seed misses one counting item to create contrast.
            val = ans if not (self.cfg.name == "seed" and item["id"] == "g02_count") else ans - 1
            return ChatResult(self.cfg.name, self.cfg.model, str(val), latency, ok=True)
        if task == "vqa_keyword":
            txt = (ans[0] if isinstance(ans, list) else str(ans))
            return ChatResult(self.cfg.name, self.cfg.model, f"The answer is {txt}.", latency, ok=True)
        if task == "open_ended":
            return ChatResult(self.cfg.name, self.cfg.model, str(ans), latency, ok=True)
        return ChatResult(self.cfg.name, self.cfg.model, "ok", latency, ok=True)
