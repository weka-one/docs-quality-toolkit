"""Adjudication layer, including the properties that keep the eval honest."""
import json
import pathlib

from freshness.detect import Finding
from freshness.llm import (
    HeuristicAdjudicator,
    NullAdjudicator,
    RecordedAdjudicator,
    _cache_key,
    apply,
    build,
    page_context,
)


def finding(**kw):
    base = dict(
        detector="unknown_endpoint", page="p.mdx", line=3,
        message="not in spec", confidence=0.35, evidence="GET /x",
        needs_review=True,
    )
    base.update(kw)
    return Finding(**base)


def test_null_adjudicator_abstains():
    assert NullAdjudicator().adjudicate(finding(), "") is None


def test_adjudicators_never_touch_confident_findings():
    """Only uncertain findings are sent for review; a confident detector result
    must not be second-guessed by a heuristic or a model."""
    confident = finding(confidence=0.9, needs_review=False)
    assert HeuristicAdjudicator().adjudicate(confident, "github.com") is None


def test_heuristic_dismisses_third_party_hosts():
    verdict = HeuristicAdjudicator().adjudicate(
        finding(evidence="GET /meilisearch/meilisearch/latest/config.toml",
                base="https://raw.githubusercontent.com"),
        "",
    )
    assert verdict is not None and verdict.actionable is False


def test_heuristic_ignores_unrelated_mentions_in_surrounding_prose():
    """A page that links to GitHub somewhere must not have its real findings
    dismissed. The verdict comes from the sample's own base URL."""
    assert HeuristicAdjudicator().adjudicate(
        finding(evidence="POST /indexes/deals/delete-by-filter", base="MEILISEARCH_URL"),
        "See https://github.com/meilisearch/meilisearch for the source.",
    ) is None


def test_heuristic_abstains_on_first_party_paths():
    assert HeuristicAdjudicator().adjudicate(
        finding(evidence="POST /indexes/deals/delete-by-filter", base="MEILISEARCH_URL"),
        "curl -X POST 'MEILISEARCH_URL/indexes/deals/delete-by-filter'",
    ) is None


def test_recorded_cache_key_changes_with_evidence():
    """A changed finding must miss the cache rather than silently reuse a
    verdict about different evidence."""
    a = _cache_key(finding(evidence="GET /a"), "ctx")
    b = _cache_key(finding(evidence="GET /b"), "ctx")
    assert a != b


def test_recorded_adjudicator_replays_and_counts_misses(tmp_path):
    f = finding()
    cache = {_cache_key(f, "ctx"): {"actionable": False, "confidence": 0.8, "reason": "r"}}
    path = tmp_path / "cache.json"
    path.write_text(json.dumps(cache))

    rec = RecordedAdjudicator(path)
    assert rec.adjudicate(f, "ctx").actionable is False
    assert rec.hits == 1

    # A miss must be counted, not silently degraded to "abstain": an eval that
    # quietly falls back reports the deterministic baseline while claiming to
    # measure the model.
    assert rec.adjudicate(finding(evidence="GET /other"), "ctx") is None
    assert rec.misses == 1


def test_missing_cache_file_is_not_an_error(tmp_path):
    rec = RecordedAdjudicator(tmp_path / "absent.json")
    assert rec.adjudicate(finding(), "ctx") is None


def test_apply_drops_dismissed_and_keeps_confirmed():
    findings = [
        finding(evidence="GET /meilisearch/meilisearch/latest/config.toml",
                base="https://raw.githubusercontent.com"),
        finding(evidence="POST /indexes/deals/delete-by-filter", base="MEILISEARCH_URL"),
        finding(confidence=0.9, needs_review=False, evidence="POST /indexes/x"),
    ]
    result = apply(HeuristicAdjudicator(), findings, {"p.mdx": "some page text"})
    kept = {f.evidence for f in result["findings"]}
    assert "GET /meilisearch/meilisearch/latest/config.toml" not in kept
    assert "POST /indexes/deals/delete-by-filter" in kept
    assert result["dropped"] == 1


def test_page_context_is_bounded():
    text = "\n".join(str(i) for i in range(200))
    assert len(page_context(text, 100, radius=5).split("\n")) <= 11


def test_build_rejects_unknown_backend():
    import pytest

    with pytest.raises(ValueError):
        build("telepathy")
