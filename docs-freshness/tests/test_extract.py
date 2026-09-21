"""Extraction decides what can be checked at all."""
import pytest

from freshness.extract import (
    _is_enum_candidate,
    _split_continuations,
    extract,
    parse_curl,
)


def test_parses_method_path_and_base():
    parsed = parse_curl("curl -X POST 'MEILISEARCH_URL/indexes/movies/search' -H 'Authorization: Bearer K'")
    assert parsed["method"] == "POST"
    assert parsed["path"] == "/indexes/movies/search"
    assert parsed["base"] == "MEILISEARCH_URL"


def test_implicit_get():
    assert parse_curl("curl 'MEILISEARCH_URL/health'")["method"] == "GET"


def test_braced_and_dollar_placeholders():
    for url in ("${MEILISEARCH_URL}/health", "$MEILI_HOST/health"):
        assert parse_curl(f"curl '{url}'")["path"] == "/health"


def test_real_host_is_kept_as_base():
    parsed = parse_curl("curl 'https://raw.githubusercontent.com/meilisearch/x/config.toml'")
    assert parsed["base"] == "https://raw.githubusercontent.com"
    assert parsed["path"] == "/meilisearch/x/config.toml"


def test_query_string_split_from_path():
    parsed = parse_curl("curl 'MEILISEARCH_URL/indexes/m/stats?sizeFormat=human&x=1'")
    assert parsed["path"] == "/indexes/m/stats"
    assert parsed["query"] == "sizeFormat=human&x=1"


def test_multiline_quoted_body_is_not_truncated():
    """A JSON body spanning lines inside single quotes, with no backslashes.
    Splitting on newlines alone drops it entirely."""
    block = (
        "curl -X PATCH \\\n"
        "  'MEILISEARCH_URL/indexes/p/settings' \\\n"
        "  --data-binary '{\n"
        '    "searchableAttributes": ["title"],\n'
        '    "rankingRules": ["words"]\n'
        "  }'\n"
    )
    commands = _split_continuations(block)
    parsed = parse_curl(commands[0][0])
    import json

    body = json.loads(parsed["body"])
    assert set(body) == {"searchableAttributes", "rankingRules"}


def test_body_params_extracted_from_page():
    page = (
        "---\ntitle: t\n---\n\n"
        "```bash\ncurl -X POST 'MEILISEARCH_URL/indexes/m/search' "
        "--data-binary '{\"q\": \"x\", \"limit\": 5}'\n```\n"
    )
    names = {c.name for c in extract("p.mdx", page) if c.kind == "body_param"}
    assert names == {"q", "limit"}


def test_auth_presence_detected():
    page = (
        "---\ntitle: t\n---\n\n```bash\ncurl 'MEILISEARCH_URL/keys' "
        "-H 'Authorization: Bearer K'\n```\n"
    )
    auth = [c for c in extract("p.mdx", page) if c.kind == "auth"]
    assert auth and auth[0].has_auth is True


def test_inline_route_claim_is_marked_as_prose():
    page = "---\ntitle: t\n---\n\nUse the `POST /events` endpoint.\n"
    claims = [c for c in extract("p.mdx", page) if c.kind == "endpoint"]
    assert len(claims) == 1
    assert claims[0].origin == "inline"
    assert claims[0].path == "/events"


def test_route_marker_claim():
    page = '---\ntitle: t\n---\n\n<RouteHighlighter method="POST" path="/events" />\n'
    claims = [c for c in extract("p.mdx", page) if c.kind == "endpoint"]
    assert claims and claims[0].origin == "route_marker"


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("statuses", "enqueued", True),
        ("matchingStrategy", "last", True),
        # The field referring to itself. `rstrip("s")` turns "statuses" into
        # "statuse" and lets this through.
        ("statuses", "status", False),
        ("types", "type", False),
        # A dotted settings path from a migration mapping table.
        ("sortFacetValuesBy", "faceting.sortFacetValuesBy", False),
        # The type column.
        ("limit", "integer", False),
        ("offset", "20", False),
    ],
)
def test_enum_candidate_filter(field, value, expected):
    assert _is_enum_candidate(field, value) is expected


def test_code_blocks_that_are_not_shell_are_skipped():
    page = "---\ntitle: t\n---\n\n```python\nclient.search('curl /indexes/x')\n```\n"
    assert not [c for c in extract("p.mdx", page) if c.kind == "endpoint"]
