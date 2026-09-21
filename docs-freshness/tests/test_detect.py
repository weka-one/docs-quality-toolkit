"""Detector behaviour, including the cases where it must stay silent.

The silent cases carry the weight. A freshness checker is used by writers who
did not build it, and one confident false positive teaches them to ignore it.
"""
import pathlib

from freshness.detect import Detectors, default_bases
from freshness.extract import extract


def run(spec, page_text, bases=None, page="p.mdx"):
    claims = extract(page, page_text)
    detectors = Detectors(spec, bases)
    return detectors, detectors.run(claims)


def sample(path, method="GET", auth=True, body=None, base="MEILISEARCH_URL"):
    header = " -H 'Authorization: Bearer K'" if auth else ""
    data = f" --data-binary '{body}'" if body else ""
    return (
        "---\ntitle: t\n---\n\n```bash\n"
        f"curl -X {method} '{base}{path}'{header}{data}\n```\n"
    )


def test_known_endpoint_is_silent(spec):
    _, findings = run(spec, sample("/indexes/movies/documents"))
    assert findings == []


def test_unknown_method_on_known_path(spec):
    _, findings = run(spec, sample("/indexes/movies", method="POST"))
    hit = [f for f in findings if f.detector == "unknown_endpoint"]
    assert hit and hit[0].confidence >= 0.9
    assert "only for" in hit[0].message


def test_unknown_body_parameter_suggests_nearest(spec):
    _, findings = run(spec, sample(
        "/indexes/movies/search", method="POST", body='{"matchingStratergy": "last"}'
    ))
    hit = [f for f in findings if f.detector == "unknown_parameter"]
    assert hit and hit[0].suggestion == "matchingStrategy"


def test_valid_body_parameter_is_silent(spec):
    _, findings = run(spec, sample(
        "/indexes/movies/search", method="POST", body='{"matchingStrategy": "last", "q": "x"}'
    ))
    assert [f for f in findings if f.detector == "unknown_parameter"] == []


def test_missing_auth_on_secured_operation(spec):
    _, findings = run(spec, sample("/indexes/movies/documents", auth=False))
    assert any(f.detector == "missing_auth" for f in findings)


def test_auth_present_is_silent(spec):
    _, findings = run(spec, sample("/indexes/movies/documents", auth=True))
    assert not any(f.detector == "missing_auth" for f in findings)


def test_base_scoping_skips_other_services(spec):
    """A GitHub release download reduces to a plausible-looking path once the
    host is stripped. Without scoping it is reported as missing from the spec:
    true, and useless."""
    page = sample("/meilisearch/meilisearch/latest/config.toml",
                  base="https://raw.githubusercontent.com", auth=False)
    detectors, findings = run(spec, page, bases={"", "MEILISEARCH_URL"})
    assert findings == []
    assert detectors.out_of_scope > 0

    _, unscoped = run(spec, page, bases=None)
    assert any(f.detector == "unknown_endpoint" for f in unscoped)


def test_inline_prose_route_is_flagged_for_review_not_asserted(spec):
    """Prose carries no base URL, and a migration guide names a competitor's
    routes in identical syntax."""
    page = "---\ntitle: t\n---\n\nUse the `POST /events` endpoint.\n"
    _, findings = run(spec, page, bases={"", "MEILISEARCH_URL"})
    hit = [f for f in findings if f.detector == "unknown_endpoint"]
    assert hit
    assert hit[0].needs_review is True
    assert hit[0].confidence < 0.6


def test_route_marker_is_trusted_like_a_sample(spec):
    page = '---\ntitle: t\n---\n\n<RouteHighlighter method="POST" path="/events" />\n'
    _, findings = run(spec, page, bases={"", "MEILISEARCH_URL"})
    assert any(f.detector == "unknown_endpoint" for f in findings)


def test_abstains_when_operation_declares_no_body_schema(spec):
    """Silence beats a guess: the spec simply does not describe that surface."""
    detectors, findings = run(spec, sample("/dumps", method="POST", body='{"anything": 1}'))
    assert [f for f in findings if f.detector == "unknown_parameter"] == []
    assert detectors.abstentions


def test_enum_value_outside_the_spec(spec):
    page = (
        "---\ntitle: t\n---\n\n"
        "| Name | Description |\n| --- | --- |\n"
        "| `matchingStrategy` | One of `last`, `all`, or `fuzzy`. |\n"
    )
    _, findings = run(spec, page)
    hit = [f for f in findings if f.detector == "unknown_enum_value"]
    assert len(hit) == 1
    assert "fuzzy" in hit[0].evidence


def test_valid_enum_values_are_silent(spec):
    page = (
        "---\ntitle: t\n---\n\n"
        "| Name | Description |\n| --- | --- |\n"
        "| `matchingStrategy` | One of `last`, `all`, or `frequency`. |\n"
    )
    _, findings = run(spec, page)
    assert [f for f in findings if f.detector == "unknown_enum_value"] == []


def test_default_bases_includes_spec_servers(spec):
    bases = default_bases(spec, [])
    assert "localhost:7700" in bases or "http://localhost:7700" in bases


def test_findings_are_deduplicated(spec):
    """One curl line yields endpoint and auth claims; a page repeating the same
    call must not report the same defect twice."""
    page = sample("/indexes/movies", method="POST") * 1
    page += "\n```bash\ncurl -X POST 'MEILISEARCH_URL/indexes/movies' -H 'Authorization: Bearer K'\n```\n"
    _, findings = run(spec, page)
    keys = [f.key for f in findings]
    assert len(keys) == len(set(keys))
