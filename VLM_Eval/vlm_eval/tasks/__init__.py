"""Task registry: maps a manifest item's ``task`` field to a scorer."""
from __future__ import annotations

from .base import EvalItem, ItemScore
from .director3d import Director3DTask
from .general import KeywordVQATask, NumericVQATask, OpenEndedTask

TASKS = {
    "director3d": Director3DTask(),
    "vqa_numeric": NumericVQATask(),
    "vqa_keyword": KeywordVQATask(),
    "open_ended": OpenEndedTask(),
}


def get_task(name: str):
    if name not in TASKS:
        raise KeyError(f"Unknown task '{name}'. Known: {sorted(TASKS)}")
    return TASKS[name]


__all__ = ["EvalItem", "ItemScore", "TASKS", "get_task"]
