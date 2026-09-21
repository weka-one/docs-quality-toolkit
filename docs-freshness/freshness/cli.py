#!/usr/bin/env python3
"""Check documentation against an OpenAPI specification.

    python -m freshness --docs ../corpus/meilisearch-docs --spec ../spec/meilisearch-openapi.json

Findings are split at a confidence gate rather than reported as one list. The
evaluation harness measures where that gate belongs: on the vendored corpus,
0.6 gives precision 1.00 at recall 0.76, while reporting everything gives
precision 0.41. The findings below the gate are not thrown away -- they go to a
review queue, optionally adjudicated by `--adjudicator`.

A checker that fails a build on its low-confidence output gets switched off in
a week. A checker that silently drops it misses real drift. The gate is how you
get both.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from . import llm, report
from .detect import Detectors, default_bases
from .extract import extract
from .spec import Spec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="freshness", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--docs", required=True, type=pathlib.Path)
    ap.add_argument("--spec", required=True, type=pathlib.Path)
    ap.add_argument("--min-confidence", type=float, default=0.6,
                    help="gate: findings at or above this fail the run (default 0.6)")
    ap.add_argument("--adjudicator", default="none",
                    choices=["none", "heuristic", "recorded", "claude"],
                    help="resolve review-queue findings (default: none)")
    ap.add_argument("--llm-cache", type=pathlib.Path,
                    help="replay/record file for the adjudicator")
    ap.add_argument("--base", action="append", dest="bases",
                    help="base URL or placeholder that identifies this API; repeatable. "
                         "Defaults to the spec's servers plus the corpus's dominant placeholder.")
    ap.add_argument("--suggest-bases", action="store_true",
                    help="print the base URLs found in the corpus and exit")
    ap.add_argument("--format", default="markdown", choices=["markdown", "json", "sarif"])
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--fail-on-findings", action="store_true",
                    help="exit 1 if anything is at or above the gate")
    args = ap.parse_args(argv)

    if not args.docs.is_dir():
        sys.exit(f"docs directory not found: {args.docs}")
    if not args.spec.is_file():
        sys.exit(f"spec file not found: {args.spec}")

    spec = Spec.load(args.spec)
    pages = {
        str(p.relative_to(args.docs)): p.read_text(encoding="utf-8")
        for p in sorted([*args.docs.rglob("*.mdx"), *args.docs.rglob("*.md")])
    }
    claims = [c for page, text in pages.items() for c in extract(page, text)]

    if args.suggest_bases:
        import collections

        counts = collections.Counter(c.base for c in claims if c.base and c.kind == "endpoint")
        print("Base URLs and placeholders found in code samples:\n")
        for base, n in counts.most_common():
            print(f"  {n:5}  {base}")
        print("\nPass the ones that identify this API with --base (repeatable).")
        return 0

    bases = set(args.bases) | {""} if args.bases else default_bases(spec, claims)
    detectors = Detectors(spec, bases)
    findings = detectors.run(claims)

    adjudicator = llm.build(args.adjudicator, args.llm_cache)
    outcome = llm.apply(adjudicator, findings, pages)
    findings = outcome["findings"]

    gated = [f for f in findings if f.confidence >= args.min_confidence]
    review = [f for f in findings if f.confidence < args.min_confidence]

    stats = {
        "pages": len(pages),
        "spec_title": spec.title,
        "spec_version": spec.version,
        "operations": len(spec.operations),
        "min_confidence": args.min_confidence,
        "out_of_scope": detectors.out_of_scope,
        "abstentions": len(detectors.abstentions),
        "bases": sorted(b for b in bases if b),
        "adjudicator": outcome["adjudicator"],
        "adjudicated": outcome["reviewed"],
        "dismissed": outcome["dropped"],
    }

    renderer = {"markdown": report.to_markdown, "json": report.to_json, "sarif": report.to_sarif}
    text = renderer[args.format](gated, review, stats)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"wrote {args.out} ({len(gated)} finding(s), {len(review)} queued for review)")
    else:
        print(text)

    return 1 if (args.fail_on_findings and gated) else 0


if __name__ == "__main__":
    raise SystemExit(main())
