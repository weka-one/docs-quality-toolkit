#!/usr/bin/env python3
"""Recover page text from a JSON payload embedded in the HTML.

Some sites render in the browser but still ship every page's content inside an
inline `<script>` as JSON. developers.tiktok.com is one: a Modern.js app whose
`_ROUTER_DATA` island carries 77 KB of JSON per page while the HTML itself
reduces to 161 words.

That makes the content recoverable without a headless browser. What it does not
make it is *predictable*: nothing here assumes a field called `content` or a
particular nesting. The extractor walks whatever JSON is there and scores every
string it finds on how much it looks like documentation prose, so a site that
reshapes its payload next quarter still works.

    pipeline/json_island.py page.html --inspect   # what is in there
    pipeline/json_island.py page.html             # the recovered text
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from pipeline.probe import SCRIPT_BLOCK, PAYLOAD_NAME  # noqa: E402

# Markers of prose a reader would see, rather than configuration or ids.
PROSE_HINTS = re.compile(r"(?m)(^#{1,6}\s|\n\n|```|\. [A-Z]|, |\bthe\b|\byou\b)")
# Values that are plainly machine data, whatever their length.
NOT_PROSE = re.compile(
    r"^(?:https?://|/|[A-Za-z0-9+/=]{60,}$|[0-9a-f]{32,}$|\{|\[|#[0-9a-f]{3,8}$)"
)


def parse_islands(html: str) -> list[tuple[str, object]]:
    """Every inline script that parses as JSON, with the name it sits under."""
    islands = []
    for attrs, body in SCRIPT_BLOCK.findall(html):
        if not body.strip():
            continue
        match = PAYLOAD_NAME.search(attrs) or PAYLOAD_NAME.search(body[:400])
        name = next((g for g in (match.groups() if match else ()) if g), "(anonymous)")

        # Either the whole block is JSON, or it is `something = { ... };`
        candidate = body.strip()
        if not candidate.startswith(("{", "[")):
            eq = candidate.find("=")
            if eq == -1:
                continue
            candidate = candidate[eq + 1:].strip().rstrip(";").strip()
        if not candidate.startswith(("{", "[")):
            continue
        try:
            islands.append((name, json.loads(candidate)))
        except (ValueError, RecursionError):
            continue
    return islands


def walk_strings(node, path=""):
    """Yield (json path, string) for every string in the structure."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from walk_strings(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk_strings(value, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def prose_score(text: str) -> float:
    """How much this string looks like something a reader would read."""
    stripped = text.strip()
    if len(stripped) < 80 or NOT_PROSE.match(stripped):
        return 0.0
    hits = len(PROSE_HINTS.findall(stripped))
    spaces = stripped.count(" ") / max(1, len(stripped))
    # Prose is mostly spaces-and-words; a token blob or a URL list is not.
    if spaces < 0.05:
        return 0.0
    return hits * (len(stripped) ** 0.5) * spaces


def recover(html: str, limit: int = 40) -> tuple[str, list[tuple[str, str, int, float]]]:
    """Return (recovered text, ranked candidates) from a page's JSON islands."""
    ranked = []
    for name, data in parse_islands(html):
        for path, value in walk_strings(data):
            score = prose_score(value)
            if score > 0:
                ranked.append((name, path, len(value), score, value))
    ranked.sort(key=lambda r: -r[3])
    kept = ranked[:limit]

    seen, parts = set(), []
    for _, _, _, _, value in kept:
        key = value.strip()[:200]
        if key in seen:
            continue
        seen.add(key)
        parts.append(value.strip())
    return "\n\n".join(parts), [(n, p, l, s) for n, p, l, s, _ in kept]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("page", type=pathlib.Path, help="an HTML file saved by the probe")
    ap.add_argument("--inspect", action="store_true",
                    help="show what is in the payload instead of the recovered text")
    ap.add_argument("--out", type=pathlib.Path, help="write the recovered text here")
    args = ap.parse_args()

    if not args.page.is_file():
        print(f"No file at {args.page}", file=sys.stderr)
        return 1
    html = args.page.read_text(encoding="utf-8", errors="replace")

    islands = parse_islands(html)
    if not islands:
        print("No inline script parsed as JSON. Nothing to recover here.", file=sys.stderr)
        return 1

    text, ranked = recover(html)

    if args.inspect:
        print(f"\nJSON islands in {args.page.name}:\n")
        for name, data in islands:
            count = sum(1 for _ in walk_strings(data))
            print(f"  {name}: parsed, {count:,} strings inside")
        print(f"\nTop text found, by how much it reads like documentation:\n")
        for name, path, length, score in ranked[:15]:
            print(f"  {score:9.0f}  {length:>7,} chars  {name}.{path[:70]}")
        words = len(re.findall(r"\b\w+\b", text))
        print(f"\n  recovered {words:,} words total")
        print("\nFirst 400 characters of what came back:\n")
        print("  " + text[:400].replace("\n", "\n  "))
        print()
        return 0

    if args.out:
        args.out.write_text(text, encoding="utf-8")
        words = len(re.findall(r"\b\w+\b", text))
        print(f"wrote {args.out} ({words:,} words)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
