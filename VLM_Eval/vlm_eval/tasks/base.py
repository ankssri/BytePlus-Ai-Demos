"""Base types for eval items and scoring."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..providers import ChatClient, ChatResult


@dataclass
class EvalItem:
    """One row of a dataset manifest."""

    id: str
    task: str
    image: str                      # path relative to the manifest's directory
    tags: list[str] = field(default_factory=list)
    track: str = "synthetic"        # "synthetic" (exact GT) or "real" (hand-labeled)
    prompt: Optional[str] = None    # overrides the task's default prompt
    ground_truth: Optional[Any] = None
    answer: Optional[Any] = None    # for VQA-style tasks
    meta: dict = field(default_factory=dict)

    _base_dir: Optional[Path] = None

    @property
    def image_path(self) -> str:
        base = self._base_dir or Path(".")
        return str(base / self.image)

    @classmethod
    def from_dict(cls, d: dict, base_dir: Path) -> "EvalItem":
        return cls(
            id=d["id"],
            task=d["task"],
            image=d["image"],
            tags=d.get("tags", []),
            track=d.get("track", "synthetic"),
            prompt=d.get("prompt"),
            ground_truth=d.get("ground_truth"),
            answer=d.get("answer"),
            meta=d.get("meta", {}),
            _base_dir=base_dir,
        )


@dataclass
class ItemScore:
    """Scoring output for one (item, provider, repeat) call."""

    composite: Optional[float]           # None if the call produced nothing scorable
    metrics: dict                        # named sub-metrics in [0,1]
    valid: bool                          # produced a usable/parseable answer
    latency_s: float
    attempts: int
    error: Optional[str] = None
    notes: list[str] = field(default_factory=list)   # human-readable error chips
    prediction: Optional[Any] = None     # parsed prediction (for debugging/UI)
    raw_text: str = ""


class Task:
    """A task knows how to prompt a model and score the reply."""

    name: str = "base"
    expect_json: bool = False

    def default_prompt(self, item: EvalItem) -> str:
        raise NotImplementedError

    def run(self, client: ChatClient, item: EvalItem, judge: "ChatClient | None" = None) -> ItemScore:
        raise NotImplementedError

    # helper used by subclasses
    def _call(self, client: ChatClient, item: EvalItem, prompt: str,
              json_object: bool = False, max_tokens: int = 2048) -> ChatResult:
        return client.chat(
            prompt,
            image_paths=[item.image_path],
            expect_json=self.expect_json,
            json_object=json_object,
            max_tokens=max_tokens,
        )
