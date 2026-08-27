"""General VLM tasks: numeric VQA, keyword VQA, and open-ended (LLM-judged)."""
from __future__ import annotations

import re
from typing import Optional

from ..providers import ChatClient
from .base import EvalItem, ItemScore, Task
from ..utils import extract_json

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


class NumericVQATask(Task):
    """Answer is a number (e.g. counting). Exact match unless a tolerance is set."""

    name = "vqa_numeric"
    expect_json = False

    def default_prompt(self, item: EvalItem) -> str:
        q = item.meta.get("question", "Answer the question about the image.")
        return f"{q}\nAnswer with a single number only."

    def run(self, client: ChatClient, item: EvalItem, judge: Optional[ChatClient] = None) -> ItemScore:
        prompt = item.prompt or self.default_prompt(item)
        res = client.chat(prompt, image_paths=[item.image_path], max_tokens=64)
        if not res.ok:
            return ItemScore(None, {}, False, res.latency_s, res.attempts,
                             error=res.error, notes=["call failed"], raw_text=res.text)
        nums = _NUM_RE.findall(res.text)
        if not nums:
            return ItemScore(0.0, {"exact": 0.0}, True, res.latency_s, res.attempts,
                             notes=["no number in answer"], raw_text=res.text)
        pred = float(nums[0])
        target = float(item.answer)
        tol = float(item.meta.get("tolerance", 0))
        correct = abs(pred - target) <= tol
        return ItemScore(
            composite=1.0 if correct else 0.0,
            metrics={"exact": 1.0 if correct else 0.0},
            valid=True, latency_s=res.latency_s, attempts=res.attempts,
            notes=[] if correct else [f"got {pred:g}, expected {target:g}"],
            prediction=pred, raw_text=res.text,
        )


class KeywordVQATask(Task):
    """Answer accepted if any of the accepted strings appears (normalized)."""

    name = "vqa_keyword"
    expect_json = False

    def default_prompt(self, item: EvalItem) -> str:
        q = item.meta.get("question", "Answer the question about the image.")
        return f"{q}\nAnswer concisely."

    def run(self, client: ChatClient, item: EvalItem, judge: Optional[ChatClient] = None) -> ItemScore:
        prompt = item.prompt or self.default_prompt(item)
        res = client.chat(prompt, image_paths=[item.image_path], max_tokens=128)
        if not res.ok:
            return ItemScore(None, {}, False, res.latency_s, res.attempts,
                             error=res.error, notes=["call failed"], raw_text=res.text)
        accepted = item.answer if isinstance(item.answer, list) else [item.answer]
        hay = _normalize(res.text)
        hit = any(_normalize(str(a)) in hay for a in accepted)
        return ItemScore(
            composite=1.0 if hit else 0.0,
            metrics={"match": 1.0 if hit else 0.0},
            valid=True, latency_s=res.latency_s, attempts=res.attempts,
            notes=[] if hit else [f"missing {accepted!r}"],
            prediction=res.text.strip()[:120], raw_text=res.text,
        )


_JUDGE_PROMPT = """You are grading an AI's answer to a question about an image.

Question: {q}
Reference / rubric: {ref}
AI answer: {ans}

Score the AI answer from 0 to 5 for correctness and completeness against the
reference. Return ONLY JSON: {{"score": <0-5 integer>, "reason": "<short>"}}"""


class OpenEndedTask(Task):
    """Open-ended answer graded 0-5 by a judge model, normalized to [0,1]."""

    name = "open_ended"
    expect_json = False

    def default_prompt(self, item: EvalItem) -> str:
        return item.meta.get("question", "Describe the image in detail.")

    def run(self, client: ChatClient, item: EvalItem, judge: Optional[ChatClient] = None) -> ItemScore:
        prompt = item.prompt or self.default_prompt(item)
        res = client.chat(prompt, image_paths=[item.image_path], max_tokens=512)
        if not res.ok:
            return ItemScore(None, {}, False, res.latency_s, res.attempts,
                             error=res.error, notes=["call failed"], raw_text=res.text)
        if judge is None:
            # No judge configured: record the answer but leave it unscored.
            return ItemScore(None, {}, True, res.latency_s, res.attempts,
                             notes=["no judge configured"],
                             prediction=res.text.strip()[:200], raw_text=res.text)
        jprompt = _JUDGE_PROMPT.format(
            q=prompt,
            ref=item.answer or item.meta.get("rubric", "a faithful, detailed answer"),
            ans=res.text.strip(),
        )
        jres = judge.chat(jprompt, image_paths=[item.image_path], expect_json=True,
                          json_object=True, max_tokens=256)
        obj = jres.json_obj or extract_json(jres.text) or {}
        try:
            score5 = float(obj.get("score", 0))
        except (TypeError, ValueError):
            score5 = 0.0
        score = max(0.0, min(1.0, score5 / 5.0))
        reason = str(obj.get("reason", ""))[:120]
        return ItemScore(
            composite=score,
            metrics={"judge": score},
            valid=True, latency_s=res.latency_s, attempts=res.attempts,
            notes=[reason] if reason else [],
            prediction=res.text.strip()[:200], raw_text=res.text,
        )


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()
