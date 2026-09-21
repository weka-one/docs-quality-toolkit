"""Extract checkable claims about an API from a documentation page.

A "claim" is any statement in the docs that the OpenAPI spec can adjudicate:
this endpoint exists, this request body takes this field, this parameter
accepts these values, this call needs authentication.

Only claims that can be *falsified* are extracted. Prose describing what a
parameter means is not a claim, because nothing in the spec can contradict it
without a judgement call -- that is what the optional LLM layer is for.

Everything carries a line number. A finding a writer cannot navigate to is a
finding they will not fix.
"""
from __future__ import annotations

import dataclasses
import json
import re
import shlex
from typing import Iterator

FENCE = re.compile(r"^(?P<indent>[ \t]*)```(?P<lang>[\w+-]*)[^\n]*\n(?P<body>.*?)^(?P=indent)```", re.M | re.S)
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)

# Hosts and placeholders that stand in for a deployment's base URL.
BASE_URL = re.compile(
    r"""(?:
          \$\{[A-Z_][A-Z0-9_]*\}          # ${MEILISEARCH_URL}
        | \$[A-Z_][A-Z0-9_]*              # $MEILI_HOST
        | https?://[^/'"\s]+              # http://localhost:7700
        | [A-Z][A-Z0-9_]{2,}              # MEILISEARCH_URL, HOST, URL
        )""",
    re.VERBOSE,
)

CLAIM_KINDS = (
    "endpoint",
    "body_param",
    "query_param",
    "enum_value",
    "auth",
)


@dataclasses.dataclass
class Claim:
    kind: str
    page: str
    line: int
    method: str = ""
    path: str = ""
    name: str = ""          # parameter or field name
    base: str = ""          # base URL or placeholder the sample targets
    origin: str = "curl"    # curl | inline | route_marker
    value: str = ""         # enum value
    field: str = ""         # field an enum value belongs to
    snippet: str = ""
    has_auth: bool | None = None

    def location(self) -> str:
        return f"{self.page}:{self.line}"


def _strip_frontmatter(text: str) -> tuple[str, int]:
    m = FRONTMATTER.match(text)
    return (text[m.end():], text[: m.end()].count("\n")) if m else (text, 0)


def iter_code_blocks(text: str) -> Iterator[tuple[str, str, int]]:
    """Yield (language, body, starting line number) for each fenced block."""
    for m in FENCE.finditer(text):
        line = text[: m.start("body")].count("\n") + 1
        yield m.group("lang").lower(), m.group("body"), line


def _split_continuations(block: str) -> list[tuple[str, int]]:
    """Split a shell block into commands, tracking each one's starting line.

    Two things end a command, and both must be checked. A trailing backslash
    continues it, and so does an unterminated quote: these samples routinely
    pass a multi-line JSON body inside a single-quoted string with no
    backslashes at all --

        curl -X PATCH 'URL/indexes/products/settings' \
          --data-binary '{
            "searchableAttributes": ["title"]
          }'

    Splitting on newlines alone truncates that at `--data-binary '{`, which
    silently drops the body. Before this handled quotes, 493 curl invocations
    in the corpus yielded 192 endpoint claims and 23 body parameters.

    """
    out: list[tuple[str, int]] = []
    buf: list[str] = []
    start = 0
    quote: str | None = None

    for offset, raw in enumerate(block.split("\n")):
        if not buf:
            start = offset
        line = raw.rstrip("\n")
        continues = False
        if quote is None and line.rstrip().endswith("\\"):
            line = line.rstrip()[:-1]
            continues = True

        # Track quote state across the line, honouring backslash escapes.
        escape = False
        for ch in line:
            if escape:
                escape = False
                continue
            if ch == "\\" and quote != "'":
                escape = True          # a backslash is literal inside single quotes
            elif quote is None and ch in "'\"":
                quote = ch
            elif ch == quote:
                quote = None

        buf.append(line)
        if quote is None and not continues:
            out.append((_join(buf), start))
            buf = []

    if buf:
        out.append((_join(buf), start))
    return out


def _join(parts: list[str]) -> str:
    """Join the lines of one command with spaces.

    Newlines inside a quoted body do not need preserving: the bodies we care
    about are JSON, which is whitespace-insensitive, and collapsing them keeps
    the snippet readable in a finding.
    """
    return " ".join(part.strip() for part in parts if part.strip()).strip()


def _normalise_url(raw: str) -> tuple[str, str] | None:
    """Reduce a sample URL to (base, server-relative path).

    The base matters as much as the path. A corpus contains calls to several
    different services -- the API under test, a hosted analytics endpoint on
    `https://PROJECT_URL`, release tarballs on `github.com` -- and they all
    reduce to a plausible-looking path once the host is stripped.

    Checking a GitHub download URL against the search API's spec produced
    findings like "`GET /meilisearch/meilisearch/latest/config.toml` does not
    appear in the spec": true, and completely useless. Keeping the base lets
    the detectors ignore calls that were never this API's to begin with.
    """
    url = raw.strip().strip("'\"")
    m = BASE_URL.match(url)
    base = m.group(0) if m else ""
    if m:
        url = url[m.end():]
    url = url.split("#", 1)[0]
    if not url.startswith("/"):
        return None
    return base, url


def _json_top_level_keys(blob: str) -> list[str]:
    """Top-level keys of a JSON body, tolerating sample placeholders.

    Samples are frequently not valid JSON -- they contain `...`, comments, or
    an unquoted placeholder. Falling back to a structural scan keeps those
    samples checkable instead of silently dropping them.
    """
    blob = blob.strip()
    try:
        parsed = json.loads(blob)
    except (ValueError, TypeError):
        parsed = None
    if isinstance(parsed, dict):
        return list(parsed)
    if isinstance(parsed, list):
        keys: list[str] = []
        for item in parsed:
            if isinstance(item, dict):
                keys.extend(k for k in item if k not in keys)
        return keys

    # Structural fallback: keys at brace depth 1, outside strings.
    keys, depth, i, in_string, escape = [], 0, 0, False, False
    pending_key: str | None = None
    while i < len(blob):
        ch = blob[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
                if depth == 1 and pending_key is None:
                    pending_key = blob[key_start:i]
            i += 1
            continue
        if ch == '"':
            in_string, key_start = True, i + 1
            i += 1
            continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            pending_key = None
        elif ch == ":" and depth == 1 and pending_key is not None:
            keys.append(pending_key)
            pending_key = None
        elif ch == "," and depth == 1:
            pending_key = None
        i += 1
    return keys


def parse_curl(command: str) -> dict | None:
    """Parse a curl invocation into method, path, query, headers and body."""
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if not argv or argv[0] != "curl":
        return None

    method, url, headers, body = None, None, [], None
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg in ("-X", "--request") and i + 1 < len(argv):
            method = argv[i + 1].upper()
            i += 2
        elif arg in ("-H", "--header") and i + 1 < len(argv):
            headers.append(argv[i + 1])
            i += 2
        elif arg in ("-d", "--data", "--data-raw", "--data-binary", "--data-ascii") and i + 1 < len(argv):
            body = argv[i + 1]
            i += 2
        elif arg.startswith("-"):
            i += 1
        else:
            if url is None:
                url = arg
            i += 1

    if url is None:
        return None
    normalised = _normalise_url(url)
    if normalised is None:
        return None
    base, path = normalised
    path, _, query = path.partition("?")
    return {
        "base": base,
        "method": method or "GET",
        "path": path.rstrip("/") or "/",
        "query": query,
        "headers": headers,
        "body": body,
    }


def _query_keys(query: str) -> list[str]:
    keys = []
    for part in query.split("&"):
        key = part.split("=", 1)[0].strip()
        if key and key not in keys:
            keys.append(key)
    return keys


# A markdown table row whose first cell is a code span naming a field, e.g.
#   | `matchingStrategy` | string | ... `last`, `all` ... |
TABLE_ROW = re.compile(r"^\|\s*`(?P<field>[A-Za-z_][\w.\[\]-]*)`\s*\|(?P<rest>.*)\|\s*$", re.M)
CODE_SPAN = re.compile(r"`([^`\n]+)`")
MD_LINK = re.compile(r"\[[^\]]*\]\([^)]*\)")

# `POST /indexes/{index_uid}/search` written as inline code in prose.
INLINE_ROUTE = re.compile(
    r"`(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/[A-Za-z0-9_{}/:.-]*)`"
)
# MDX route markers: <RouteHighlighter method="POST" path="/events" />
ROUTE_MARKER = re.compile(
    r"<RouteHighlighter\b[^>]*?method=[\"'](?P<method>[A-Z]+)[\"'][^>]*?"
    r"path=[\"'](?P<path>/[^\"']*)[\"'][^>]*?/?>"
)

# Type names appear in the type column of almost every parameter table and are
# never enum members.
_TYPE_WORDS = {
    "string", "integer", "int", "number", "float", "boolean", "bool", "array",
    "object", "null", "none", "any", "date", "datetime", "uuid", "n/a", "-",
}


def _is_enum_candidate(field: str, value: str) -> bool:
    """Filter code spans in a table row down to plausible enum members.

    A description cell contains far more than accepted values. Three classes of
    false positive accounted for every incorrect enum finding on the vendored
    corpus:

      `statuses` | Filter tasks by their `status`: `enqueued`, ...
          -> `status` is the field being referred to, not one of its values.

      `sortFacetValuesBy` | [`faceting.sortFacetValuesBy`](...) | setting
          -> a dotted setting path in a migration mapping table, not a value.

      `limit` | `integer` | ...
          -> the type column.
    """
    if not value or len(value) > 32:
        return False
    if re.search(r"[\s(){}\[\]:,/=]", value) or "." in value:
        return False
    if value.lower() in _TYPE_WORDS:
        return False
    if re.fullmatch(r"[-+]?\d+(\.\d+)?", value):
        return False
    # The field referring to itself, in either number. `str.rstrip("s")` is
    # wrong here -- it strips every trailing "s", turning "statuses" into
    # "statuse" and letting `status` through as a spurious enum value.
    lowered, field_lower = value.lower(), field.lower()
    variants = {field_lower, field_lower + "s", field_lower + "es"}
    if field_lower.endswith("es"):
        variants.add(field_lower[:-2])
    if field_lower.endswith("s"):
        variants.add(field_lower[:-1])
    return lowered not in variants


def extract(page: str, text: str) -> list[Claim]:
    """Extract every checkable claim from one page."""
    body, offset = _strip_frontmatter(text)
    claims: list[Claim] = []

    for lang, block, block_line in iter_code_blocks(body):
        if lang not in ("bash", "sh", "shell", "console", ""):
            continue
        for command, rel_line in _split_continuations(block):
            if "curl" not in command:
                continue
            command = command[command.index("curl"):]
            parsed = parse_curl(command)
            if not parsed:
                continue
            line = offset + block_line + rel_line
            snippet = command[:160]
            has_auth = any(h.lower().startswith("authorization:") for h in parsed["headers"])
            claims.append(
                Claim("endpoint", page, line, method=parsed["method"], path=parsed["path"],
                      base=parsed["base"], snippet=snippet, has_auth=has_auth)
            )
            claims.append(
                Claim("auth", page, line, method=parsed["method"], path=parsed["path"],
                      base=parsed["base"], snippet=snippet, has_auth=has_auth)
            )
            for key in _query_keys(parsed["query"]):
                claims.append(
                    Claim("query_param", page, line, method=parsed["method"],
                          path=parsed["path"], base=parsed["base"], name=key, snippet=snippet)
                )
            if parsed["body"]:
                for key in _json_top_level_keys(parsed["body"]):
                    claims.append(
                        Claim("body_param", page, line, method=parsed["method"],
                              path=parsed["path"], base=parsed["base"], name=key, snippet=snippet)
                    )

    # Endpoints named outside a runnable sample.
    #
    # The evaluation set caught this as a blind spot: `events_endpoint.mdx` is a
    # full reference page for `POST /events` - a route marker plus an eight-field
    # body table - and the curl-only extractor saw none of it.
    #
    # These claims are weaker evidence than a curl invocation, because prose
    # carries no base URL and a migration guide documents a competitor's routes
    # in exactly the same syntax. They are marked `origin` so the detectors can
    # treat them as uncertain rather than assert them.
    for m in INLINE_ROUTE.finditer(body):
        line = offset + body[: m.start()].count("\n") + 1
        claims.append(
            Claim("endpoint", page, line, method=m.group(1), path=m.group(2).rstrip("/") or "/",
                  origin="inline", snippet=m.group(0))
        )
    for m in ROUTE_MARKER.finditer(text):
        line = text[: m.start()].count("\n") + 1
        claims.append(
            Claim("endpoint", page, line, method=m.group("method"),
                  path=m.group("path").rstrip("/") or "/",
                  origin="route_marker", snippet=m.group(0)[:160])
        )

    # Parameter tables: a field in the first cell, its accepted values quoted
    # in the remaining cells.
    for m in TABLE_ROW.finditer(body):
        field, rest = m.group("field"), m.group("rest")
        line = offset + body[: m.start()].count("\n") + 1
        # Link targets and link text point at other pages, not at values.
        rest = MD_LINK.sub(" ", rest)
        for value in CODE_SPAN.findall(rest):
            value = value.strip()
            if _is_enum_candidate(field, value):
                claims.append(
                    Claim("enum_value", page, line, field=field, value=value,
                          snippet=m.group(0)[:160])
                )
    return claims
