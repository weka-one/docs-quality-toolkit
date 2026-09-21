#!/usr/bin/env python3
"""Turn Vale output into content-quality metrics.

Two modes:

  --target DIR                 one run; used by CI to gate a pull request
  --before DIR --after DIR     two runs; produces the before/after comparison

Counts are normalised per 1,000 prose words. Raw totals are unusable as a
quality signal across a growing doc set: adding pages raises the violation
count while leaving quality flat, so a team watching raw numbers concludes the
docs are getting worse every time someone writes something.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import valelib  # noqa: E402


def measure(target: pathlib.Path, results: dict | None = None) -> dict:
    """Compute metrics for `target`.

    `results` lets a caller supply Vale output it already has. CI runs Vale
    once and feeds the same payload to the annotator, the gate, the SARIF
    writer and this reporter; re-running it per consumer would quadruple the
    slowest step in the job.
    """
    if results is None:
        results = valelib.run_vale([str(target)])

    by_rule: collections.Counter = collections.Counter()
    by_severity: collections.Counter = collections.Counter()
    by_area: collections.Counter = collections.Counter()
    files_with_alerts = set()

    for path, alerts in results.items():
        # Vale echoes back the path exactly as it was passed on the command
        # line, which may be relative. Resolve both sides before comparing, or
        # every file lands in the same bucket.
        try:
            rel = pathlib.Path(path).resolve().relative_to(target.resolve())
        except ValueError:
            rel = pathlib.Path(path).name and pathlib.Path(pathlib.Path(path).name)
        if alerts:
            files_with_alerts.add(str(rel))
        area = rel.parts[0] if len(rel.parts) > 1 else "(root)"
        for alert in alerts:
            by_rule[alert["Check"].split(".", 1)[-1]] += 1
            by_severity[alert["Severity"]] += 1
            by_area[area] += 1

    if target.is_dir():
        files = sorted(target.rglob("*.mdx")) + sorted(target.rglob("*.md"))
    else:
        # Changed-files mode: normalise over the files Vale actually saw, not
        # the whole repository, or the per-1k-words figure is meaningless.
        files = [pathlib.Path(p) for p in results if pathlib.Path(p).exists()]
    words = sum(valelib.word_count(f.read_text(encoding="utf-8")) for f in files)
    total = sum(by_rule.values())

    return {
        "target": str(target),
        "files": len(files),
        "words": words,
        "files_with_alerts": len(files_with_alerts),
        "total": total,
        "per_1k_words": round(total / words * 1000, 2) if words else 0.0,
        "by_severity": {s: by_severity.get(s, 0) for s in valelib.SEVERITIES},
        "by_rule": dict(by_rule.most_common()),
        "by_area": dict(by_area.most_common()),
    }


def _delta(before: int, after: int) -> str:
    d = after - before
    if d == 0:
        return "0"
    pct = f" ({d / before * 100:+.0f}%)" if before else ""
    return f"{d:+d}{pct}"


def render_markdown(before: dict, after: dict | None) -> str:
    out = ["# Style linter report", ""]

    if after is None:
        out += [
            f"**{before['total']} alerts** across {before['files']} files "
            f"({before['per_1k_words']} per 1,000 words).",
            "",
            "| Severity | Count |",
            "| --- | ---: |",
        ]
        for sev in valelib.SEVERITIES:
            out.append(f"| {sev} | {before['by_severity'][sev]} |")
        out += ["", "| Rule | Count |", "| --- | ---: |"]
        for rule, n in before["by_rule"].items():
            out.append(f"| `{rule}` | {n} |")
        return "\n".join(out) + "\n"

    out += [
        f"Corpus: **{before['files']} pages, {before['words']:,} prose words**.",
        "",
        "## Totals",
        "",
        "| Metric | Before | After | Change |",
        "| --- | ---: | ---: | ---: |",
        f"| Total alerts | {before['total']} | {after['total']} | {_delta(before['total'], after['total'])} |",
        f"| Alerts per 1,000 words | {before['per_1k_words']} | {after['per_1k_words']} | "
        f"{after['per_1k_words'] - before['per_1k_words']:+.2f} |",
        f"| Files with at least one alert | {before['files_with_alerts']} | {after['files_with_alerts']} | "
        f"{_delta(before['files_with_alerts'], after['files_with_alerts'])} |",
        "",
        "## By severity",
        "",
        "| Severity | Before | After | Change |",
        "| --- | ---: | ---: | ---: |",
    ]
    for sev in valelib.SEVERITIES:
        b, a = before["by_severity"][sev], after["by_severity"][sev]
        out.append(f"| {sev} | {b} | {a} | {_delta(b, a)} |")

    out += ["", "## By rule", "", "| Rule | Before | After | Change |", "| --- | ---: | ---: | ---: |"]
    for rule in sorted(set(before["by_rule"]) | set(after["by_rule"]),
                       key=lambda r: -before["by_rule"].get(r, 0)):
        b, a = before["by_rule"].get(rule, 0), after["by_rule"].get(rule, 0)
        out.append(f"| `{rule}` | {b} | {a} | {_delta(b, a)} |")

    out += ["", "## By documentation area", "", "| Area | Before | After | Change |", "| --- | ---: | ---: | ---: |"]
    for area in sorted(set(before["by_area"]) | set(after["by_area"]),
                       key=lambda a: -before["by_area"].get(a, 0)):
        b, a = before["by_area"].get(area, 0), after["by_area"].get(area, 0)
        out.append(f"| `{area}` | {b} | {a} | {_delta(b, a)} |")

    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", type=pathlib.Path)
    ap.add_argument("--from-json", type=pathlib.Path,
                    help="use this Vale JSON instead of running Vale again")
    ap.add_argument("--before", type=pathlib.Path)
    ap.add_argument("--after", type=pathlib.Path)
    ap.add_argument("--out-json", type=pathlib.Path)
    ap.add_argument("--out-md", type=pathlib.Path)
    ap.add_argument("--fail-on", choices=["error", "warning", "suggestion", "never"], default="never")
    args = ap.parse_args()

    if args.from_json:
        results = json.loads(args.from_json.read_text() or "{}")
        before, after = measure(args.target or pathlib.Path("."), results), None
    elif args.target:
        before, after = measure(args.target), None
    elif args.before and args.after:
        before, after = measure(args.before), measure(args.after)
    else:
        ap.error("pass --target, --from-json, or both --before and --after")

    md = render_markdown(before, after)
    print(md)

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps({"before": before, "after": after}, indent=2))
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(md)

    if args.fail_on != "never":
        threshold = valelib.SEVERITIES.index(args.fail_on)
        gating = sum(
            (after or before)["by_severity"][s]
            for s in valelib.SEVERITIES[: threshold + 1]
        )
        if gating:
            print(f"\nFAIL: {gating} alert(s) at or above `{args.fail_on}`.", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
