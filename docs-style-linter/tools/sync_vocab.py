#!/usr/bin/env python3
"""Propagate the accepted vocabulary into the rules that need exceptions.

Two rules depend on knowing which capitalised words are proper nouns:

  HeadingSentenceCase  - otherwise "Install Meilisearch" looks like title case
  Acronyms             - otherwise every known initialism is reported undefined

Keeping one vocabulary file and generating both exception lists means a docs
team adds a new product name in one place. Hand-maintaining the same list in
three files is how a rule set drifts into being wrong in two of them.

The generated block is delimited by markers, so hand-written exceptions above
it survive regeneration.

Usage:
    tools/sync_vocab.py            # rewrite the rule files
    tools/sync_vocab.py --check    # fail if they are out of date (used by CI)
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
VOCAB = ROOT / "styles" / "vocabulary" / "accept.txt"
STYLES = ROOT / "styles" / "TikTokDocs"

BEGIN = "  # --- BEGIN generated from accept.txt (tools/sync_vocab.py) ---"
END = "  # --- END generated ---"


def load_vocab() -> list[str]:
    terms = []
    for line in VOCAB.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.append(line)
    return sorted(set(terms), key=str.casefold)


def is_initialism(term: str) -> bool:
    """All-caps runs of 3-5 letters, matching the Acronyms rule's `first` pattern."""
    return bool(re.fullmatch(r"[A-Z]{3,5}", term))


def render(path: pathlib.Path, terms: list[str]) -> str:
    text = path.read_text(encoding="utf-8")
    block = "\n".join([BEGIN, *(f'  - "{t}"' for t in terms), END])
    if BEGIN in text:
        return re.sub(
            re.escape(BEGIN) + r".*?" + re.escape(END), block, text, flags=re.DOTALL
        )
    if "exceptions:" not in text:
        sys.exit(f"{path.name} has no `exceptions:` key to populate")
    # `exceptions: []` is an inline empty list; appending list items under it
    # produces YAML that Vale silently refuses to load. Normalise to a bare key
    # first. The fixture preflight caught this the first time it happened.
    text = re.sub(r"^exceptions:\s*\[\s*\]\s*$", "exceptions:", text, flags=re.M)
    return text.rstrip("\n") + "\n" + block + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if files would change")
    args = ap.parse_args()

    vocab = load_vocab()
    targets = {
        STYLES / "HeadingCaseH2Plus.yml": vocab,
        STYLES / "Acronyms.yml": [t for t in vocab if is_initialism(t)],
    }

    stale = []
    for path, terms in targets.items():
        current = path.read_text(encoding="utf-8")
        updated = render(path, terms)
        if current != updated:
            stale.append(path.name)
            if not args.check:
                path.write_text(updated, encoding="utf-8")

    if args.check:
        if stale:
            print(f"out of date: {', '.join(stale)}\nRun: make vocab", file=sys.stderr)
            return 1
        print("rule exceptions are in sync with accept.txt")
        return 0

    print(f"{len(vocab)} accepted terms")
    for path, terms in targets.items():
        print(f"  {path.name}: {len(terms)} generated exception(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
