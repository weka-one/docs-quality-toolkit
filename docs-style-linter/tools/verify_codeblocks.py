#!/usr/bin/env python3
"""Prove the remediation pass did not alter a single code sample.

This is the safety property that makes automated style fixes acceptable to a
docs team. A linter that quietly rewrites `"API Key"` inside a JSON body, or
straightens a quote inside a shell command, ships broken samples to readers --
and broken samples are far more expensive than the style violation they
replaced.

Compares every fenced code block, indented code block, inline code span and
link target between two trees and fails on any difference.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import valelib  # noqa: E402


def protected_segments(text: str) -> list[str]:
    return [seg for seg, is_prose in valelib.split_prose(text) if not is_prose]


def main() -> int:
    if len(sys.argv) != 3:
        sys.exit("usage: verify_codeblocks.py <before-dir> <after-dir>")
    before, after = (pathlib.Path(a).resolve() for a in sys.argv[1:3])

    files = sorted(before.rglob("*.mdx")) + sorted(before.rglob("*.md"))
    mismatches, checked, missing = [], 0, []
    for src in files:
        dst = after / src.relative_to(before)
        if not dst.exists():
            missing.append(str(src.relative_to(before)))
            continue
        a = protected_segments(src.read_text(encoding="utf-8"))
        b = protected_segments(dst.read_text(encoding="utf-8"))
        checked += len(a)
        if a != b:
            for i, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    mismatches.append((src.relative_to(before), i, x[:120], y[:120]))
            if len(a) != len(b):
                mismatches.append(
                    (src.relative_to(before), -1, f"{len(a)} segments", f"{len(b)} segments")
                )

    if missing:
        print(f"{len(missing)} file(s) missing from the remediated tree:")
        for m in missing[:10]:
            print(f"  {m}")
        return 1
    if mismatches:
        print(f"{len(mismatches)} protected segment(s) were altered:\n")
        for path, idx, x, y in mismatches[:20]:
            print(f"  {path} [segment {idx}]\n    before: {x!r}\n    after:  {y!r}")
        return 1

    print(
        f"{checked} protected segments across {len(files)} files are byte-identical.\n"
        "No code sample, inline code span, link target, or frontmatter block was modified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
