"""Optional LLM adjudication for findings the deterministic checks cannot settle.

The deterministic detectors answer "does the spec contain this?". They cannot
answer "does this disagreement matter?", and that second question is where a
freshness checker earns or loses a writer's trust. `POST /events` really is
absent from the spec; whether that means the docs are stale or that the call
targets a different service is a judgement about context, not a lookup.

So the LLM is scoped deliberately narrowly. It never searches for drift -- a
deterministic index is faster, cheaper and exactly correct at that. It is asked
one bounded question about findings the detectors already flagged as uncertain:
would a documentation engineer have to act on this?

Four backends, all implementing the same protocol so the evaluation harness can
ablate between them:

  NullAdjudicator       abstains; the deterministic-only baseline
  HeuristicAdjudicator  hand-written rules; a non-LLM baseline that the LLM
                        must beat to justify its cost
  ClaudeAdjudicator     calls the Messages API
  RecordedAdjudicator   replays a cache captured from a real run, so CI and
                        the committed evaluation numbers are reproducible
                        offline and byte-identical

The recorded backend matters more than it looks. An evaluation whose score
moves when an external service is retrained is not a regression test.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pathlib
import re
from typing import Protocol

from .detect import Finding

MODEL = "claude-opus-5"

SYSTEM = """You review findings from a documentation freshness checker that \
compares API documentation against an OpenAPI specification.

For each finding, decide one thing: would a documentation engineer have to \
change something because of it?

Answer `actionable: true` if either the documentation or the specification \
needs a fix. Answer `actionable: false` if the finding is technically correct \
but requires no action — most commonly because the code sample calls a \
different service (a hosted analytics endpoint, a release download, a \
third-party API) and was never covered by this specification.

Judge only from the evidence given. Do not assume an endpoint exists because \
it looks plausible, and do not assume it is missing because the specification \
omits it — a generated specification can lag experimental routes. When the \
evidence genuinely does not settle it, say so with a low confidence rather \
than guessing."""


@dataclasses.dataclass
class Adjudication:
    actionable: bool
    confidence: float
    reason: str
    source: str            # which backend produced it
    cached: bool = False


class Adjudicator(Protocol):
    name: str

    def adjudicate(self, finding: Finding, context: str) -> Adjudication | None:
        """Return a verdict, or None to abstain and leave the finding as-is."""


class NullAdjudicator:
    """Abstains on everything. The deterministic-only arm of the ablation."""

    name = "none"

    def adjudicate(self, finding: Finding, context: str) -> Adjudication | None:
        return None


class HeuristicAdjudicator:
    """Hand-written rules, no model call.

    This exists to keep the LLM honest. It is easy to show that adding a model
    improves a metric; it is harder, and more useful, to show that the model
    beats the obvious rules someone would write in an afternoon. If the two
    arms score the same, the rules ship and the API bill does not.
    """

    name = "heuristic"

    # Hosts that are plainly not the API under test.
    THIRD_PARTY = re.compile(
        r"(github\.com|githubusercontent\.com|githubassets|gitlab\.com|"
        r"amazonaws\.com|googleapis\.com|cloudflare\.com|docker\.io|"
        r"npmjs\.|pypi\.org|crates\.io|PROJECT_URL|ANALYTICS)",
        re.I,
    )
    # Paths that look like file downloads rather than API resources.
    FILE_LIKE = re.compile(r"\.(json|toml|yml|yaml|tar\.gz|zip|deb|rpm|exe|sh)$", re.I)

    def adjudicate(self, finding: Finding, context: str) -> Adjudication | None:
        if not finding.needs_review:
            return None
        # Judge the sample, not the page. An earlier version matched against a
        # 25-line context window, so a single `github.com` link dismissed every
        # uncertain finding near it -- including real ones.
        if finding.base and self.THIRD_PARTY.search(finding.base):
            return Adjudication(
                False, 0.9, f"Sample targets {finding.base}, not this API.", self.name,
            )
        if self.FILE_LIKE.search(finding.evidence):
            return Adjudication(
                False, 0.8, "Path is a file download rather than an API resource.", self.name,
            )
        if finding.snippet and self.THIRD_PARTY.search(finding.snippet):
            return Adjudication(
                False, 0.7, "The sample itself names a third-party host.", self.name,
            )
        return None


def _cache_key(finding: Finding, context: str) -> str:
    payload = json.dumps(
        {
            "model": MODEL,
            "detector": finding.detector,
            "evidence": finding.evidence,
            "message": finding.message,
            "context": context,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


class RecordedAdjudicator:
    """Replays verdicts captured from a real run.

    Keyed by a hash of the exact prompt inputs, so a changed finding misses the
    cache rather than silently reusing a verdict about different evidence.
    Misses are counted and surfaced: an evaluation that quietly degrades to
    "abstain" would report the deterministic baseline while claiming to measure
    the model.
    """

    name = "recorded"

    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)
        self.cache: dict = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.hits = 0
        self.misses = 0

    def adjudicate(self, finding: Finding, context: str) -> Adjudication | None:
        if not finding.needs_review:
            return None
        entry = self.cache.get(_cache_key(finding, context))
        if entry is None:
            self.misses += 1
            return None
        self.hits += 1
        return Adjudication(
            entry["actionable"], entry["confidence"], entry["reason"],
            self.name, cached=True,
        )


class ClaudeAdjudicator:
    """Calls the Messages API, writing every verdict to a replay cache.

    Only findings the detectors marked `needs_review` are sent. On the vendored
    corpus that is a small fraction of all findings, which keeps the cost of a
    full run to a handful of calls rather than one per claim.
    """

    name = "claude"

    def __init__(self, cache_path: pathlib.Path | None = None, model: str = MODEL):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "The Claude adjudicator needs the anthropic package: pip install anthropic"
            ) from exc
        from pydantic import BaseModel

        class Verdict(BaseModel):
            actionable: bool
            confidence: float
            reason: str

        self._verdict_model = Verdict
        self.model = model
        self.client = anthropic.Anthropic()
        self.cache_path = pathlib.Path(cache_path) if cache_path else None
        self.cache: dict = {}
        if self.cache_path and self.cache_path.exists():
            self.cache = json.loads(self.cache_path.read_text())
        self.calls = 0

    def adjudicate(self, finding: Finding, context: str) -> Adjudication | None:
        if not finding.needs_review:
            return None
        key = _cache_key(finding, context)
        if key in self.cache:
            entry = self.cache[key]
            return Adjudication(
                entry["actionable"], entry["confidence"], entry["reason"],
                self.name, cached=True,
            )

        prompt = (
            f"Detector: {finding.detector}\n"
            f"Finding: {finding.message}\n"
            f"Evidence: {finding.evidence}\n"
            f"Page: {finding.page}:{finding.line}\n\n"
            f"Surrounding documentation:\n---\n{context}\n---"
        )
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
            output_format=self._verdict_model,
        )
        self.calls += 1
        verdict = response.parsed_output
        entry = {
            "actionable": verdict.actionable,
            "confidence": max(0.0, min(1.0, verdict.confidence)),
            "reason": verdict.reason,
        }
        self.cache[key] = entry
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache, indent=2, sort_keys=True))
        return Adjudication(
            entry["actionable"], entry["confidence"], entry["reason"], self.name
        )


def build(name: str, cache: pathlib.Path | None = None) -> Adjudicator:
    if name == "none":
        return NullAdjudicator()
    if name == "heuristic":
        return HeuristicAdjudicator()
    if name == "recorded":
        return RecordedAdjudicator(cache or pathlib.Path("eval/llm_cache.json"))
    if name == "claude":
        return ClaudeAdjudicator(cache or pathlib.Path("eval/llm_cache.json"))
    raise ValueError(f"unknown adjudicator: {name}")


def page_context(text: str, line: int, radius: int = 12) -> str:
    """The lines around a finding, which is what the model is asked to judge."""
    lines = text.split("\n")
    start = max(0, line - 1 - radius)
    end = min(len(lines), line + radius)
    return "\n".join(lines[start:end])


def apply(adjudicator: Adjudicator, findings: list[Finding], pages: dict[str, str]) -> dict:
    """Adjudicate uncertain findings in place. Returns a summary of what changed."""
    dropped, kept, abstained = [], [], 0
    survivors: list[Finding] = []
    for finding in findings:
        verdict = adjudicator.adjudicate(
            finding, page_context(pages.get(finding.page, ""), finding.line)
        )
        if verdict is None:
            abstained += 1
            survivors.append(finding)
            continue
        if verdict.actionable:
            # Promote: a reviewed finding that survives is no longer uncertain.
            finding.confidence = max(finding.confidence, verdict.confidence)
            finding.needs_review = False
            finding.message += f" [reviewed: {verdict.reason}]"
            kept.append(finding)
            survivors.append(finding)
        else:
            finding.message += f" [dismissed: {verdict.reason}]"
            dropped.append(finding)
    return {
        "adjudicator": getattr(adjudicator, "name", "unknown"),
        "reviewed": len(kept) + len(dropped),
        "kept": len(kept),
        "dropped": len(dropped),
        "abstained": abstained,
        "findings": survivors,
        "dropped_findings": dropped,
    }
