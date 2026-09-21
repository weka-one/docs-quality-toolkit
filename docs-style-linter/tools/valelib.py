"""Shared helpers: locating Vale, running it, and masking Markdown.

The masking layer is the load-bearing part. Vale parses Markdown and will not
apply a prose rule inside a fenced code block; `remediate.py` edits raw bytes
and has no such protection. Rewriting `API Key` to `API key` inside a JSON body,
or straightening a quote inside a shell command, turns a style fix into a broken
code sample -- the exact defect the freshness checker in ../docs-freshness/
exists to catch.

Two views of the same document:

  split_prose()               masks everything non-prose, including inline code
                              spans. Use for plain substitutions.
  split_lines_outside_code()  masks only whole-line constructs. Use for patterns
                              anchored with ^ or $, because inline masking moves
                              those anchors to mask boundaries rather than line
                              boundaries.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LINTER_ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = LINTER_ROOT / ".vale.ini"

SEVERITIES = ("error", "warning", "suggestion")


def vale_bin() -> str:
    found = shutil.which("vale")
    if found:
        return found
    fallback = pathlib.Path.home() / "go" / "bin" / "vale"
    if fallback.exists():
        return str(fallback)
    sys.exit(
        "vale not found on PATH.\n"
        "Install it with:  go install github.com/errata-ai/vale/v3/cmd/vale@v3.9.6"
    )


def run_vale(targets: list[str], config: pathlib.Path = CONFIG) -> dict:
    """Run Vale over `targets` and return its JSON payload.

    Vale exits non-zero when it finds error-level alerts, which is not a failure
    here, so `--no-exit` keeps the exit code meaningful and we read stdout.
    """
    proc = subprocess.run(
        [vale_bin(), f"--config={config}", "--output=JSON", "--no-exit", *targets],
        capture_output=True,
        text=True,
    )
    out = proc.stdout.strip()
    if not out:
        if proc.returncode not in (0, 1):
            sys.exit(f"vale failed ({proc.returncode}):\n{proc.stderr}")
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        sys.exit(f"vale produced non-JSON output:\n{out[:2000]}\n{proc.stderr}")


# --- Masking ----------------------------------------------------------------

# Whole-line constructs. Ordered so a fence is consumed before anything inside
# it can match.
_BLOCK = re.compile(
    r"""
      (?P<frontmatter>\A---\n.*?\n---\n)
    | (?P<fence>^[ \t]*(?P<mark>`{3,}|~{3,})[^\n]*\n.*?^[ \t]*(?P=mark)[ \t]*$)
    """,
    re.MULTILINE | re.DOTALL | re.VERBOSE,
)

# Inline constructs, masked only for plain substitutions.
_INLINE = re.compile(
    r"""
      (?P<code>`+[^`\n]*`+)                    # inline code span
    | (?P<jsx><[A-Za-z/][^>\n]*>)              # MDX/HTML component tag
    | (?P<target>\]\([^)\s]+(?:\s+"[^"]*")?\)) # link and image targets
    | (?P<autolink>https?://[^\s)\]]+)         # bare URL
    """,
    re.VERBOSE,
)

_INDENT_LINE = re.compile(r"^(?:[ ]{4}|\t)\S")
_LIST_ITEM = re.compile(r"^([-*+]|\d+[.)])\s")


def _indented_code_spans(text: str) -> list[tuple[int, int]]:
    """Find genuine indented code blocks.

    CommonMark requires an indented code block to be preceded by a blank line;
    it cannot interrupt a paragraph. A naive `^ {4}` match does not check that,
    and in MDX it is badly wrong: indentation is also how JSX component bodies
    and list continuations are written.

    Measured on the vendored 553-page corpus, a naive match found 539 indented
    lines outside fences, of which **zero** were code -- every one was a
    `<Card>` body or a list continuation. Masking them protected no code and
    blocked 539 lines of real prose from remediation.
    """
    spans: list[tuple[int, int]] = []
    offset, lines = 0, text.split("\n")
    offsets = []
    for line in lines:
        offsets.append(offset)
        offset += len(line) + 1

    i = 0
    while i < len(lines):
        if not _INDENT_LINE.match(lines[i]):
            i += 1
            continue
        if i == 0 or lines[i - 1].strip():
            i += 1
            continue  # not preceded by a blank line -> not a code block
        j = i - 1
        while j >= 0 and not lines[j].strip():
            j -= 1
        prev = lines[j].strip() if j >= 0 else ""
        if _LIST_ITEM.match(prev) or prev.startswith(("<", "|", ">")) or prev.endswith((">", "{")):
            i += 1
            continue  # list continuation or JSX body, not code
        start = i
        while i < len(lines) and (not lines[i].strip() or lines[i].startswith((" " * 4, "\t"))):
            i += 1
        end = i - 1
        while end > start and not lines[end].strip():
            end -= 1
        spans.append((offsets[start], offsets[end] + len(lines[end])))
    return spans


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _protected_spans(text: str, include_inline: bool) -> list[tuple[int, int]]:
    spans = [(m.start(), m.end()) for m in _BLOCK.finditer(text)]
    spans += _indented_code_spans(text)
    blocks = _merge(spans)
    if include_inline:
        covered = blocks
        for m in _INLINE.finditer(text):
            if not any(s <= m.start() < e for s, e in covered):
                spans.append((m.start(), m.end()))
    return _merge(spans)


def _split(text: str, include_inline: bool):
    pos = 0
    for start, end in _protected_spans(text, include_inline):
        if start > pos:
            yield text[pos:start], True
        yield text[start:end], False
        pos = end
    if pos < len(text):
        yield text[pos:], True


def split_prose(text: str):
    """Yield (segment, is_prose). Masks block and inline constructs."""
    return _split(text, include_inline=True)


def split_lines_outside_code(text: str):
    """Yield (segment, is_editable). Masks only whole-line constructs, so every
    boundary falls on a line boundary and ^/$ keep their real meaning."""
    return _split(text, include_inline=False)


def sub_in_prose(text: str, pattern: re.Pattern, repl) -> tuple[str, int]:
    """Apply `pattern` -> `repl` to prose segments only. Returns (text, count)."""
    out, total = [], 0
    for segment, is_prose in split_prose(text):
        if is_prose:
            segment, n = pattern.subn(repl, segment)
            total += n
        out.append(segment)
    return "".join(out), total


def _in_quotes(segment: str, index: int) -> bool:
    """True if `index` sits inside a double-quoted span on its own line.

    Documented UI strings and error messages are quoted verbatim. Deleting a
    word from one makes the docs describe a message the product never emits.
    """
    line_start = segment.rfind("\n", 0, index) + 1
    return segment.count('"', line_start, index) % 2 == 1


def sub_outside_code(
    text: str, pattern: re.Pattern, repl, skip_quoted: bool = False
) -> tuple[str, int]:
    """Apply `pattern` outside code blocks, preserving line anchoring."""
    out, total = [], 0
    for segment, editable in split_lines_outside_code(text):
        if editable:
            count = 0

            def wrapper(m: re.Match, _seg=segment):
                nonlocal count
                if skip_quoted and _in_quotes(_seg, m.start()):
                    return m.group(0)
                count += 1
                return repl(m) if callable(repl) else m.expand(repl)

            segment = pattern.sub(wrapper, segment)
            total += count
        out.append(segment)
    return "".join(out), total


def word_count(text: str) -> int:
    prose = "".join(s for s, is_prose in split_prose(text) if is_prose)
    return len(re.findall(r"\b[\w'-]+\b", prose))
