"""Render findings for humans and for CI."""
from __future__ import annotations

import collections
import json

from .detect import Finding

SEVERITY = [(0.8, "high"), (0.6, "medium"), (0.0, "low")]


def _cell(text: str) -> str:
    """Escape a value for a Markdown table cell.

    Kept as a helper because Python 3.11 rejects a backslash inside an
    f-string expression.
    """
    return text.replace("|", "\\|").replace("\n", " ")


def severity(finding: Finding) -> str:
    for floor, name in SEVERITY:
        if finding.confidence >= floor:
            return name
    return "low"


def to_markdown(gated: list[Finding], review: list[Finding], stats: dict) -> str:
    out = ["# Documentation freshness report", ""]
    out.append(
        f"Checked **{stats['pages']} pages** against **{stats['spec_title']} "
        f"{stats['spec_version']}** ({stats['operations']} operations)."
    )
    out.append("")
    if not gated and not review:
        out.append("No drift detected.")
        return "\n".join(out) + "\n"

    out += [
        f"**{len(gated)}** finding(s) at or above the gate "
        f"(confidence >= {stats['min_confidence']}), "
        f"**{len(review)}** queued for review.",
        "",
    ]

    if gated:
        out += ["## Findings", "", "| Page | Line | Detector | Confidence | Message |",
                "| --- | ---: | --- | ---: | --- |"]
        for f in gated:
            out.append(
                f"| `{f.page}` | {f.line} | `{f.detector}` | "
                f"{f.confidence:.2f} | {_cell(f.message)} |"
            )

    if review:
        out += ["", "## Review queue", "",
                "Evidence is real but does not settle whether the documentation or "
                "the spec needs changing. Most are prose mentions of routes, which "
                "carry no base URL and may belong to another product.",
                "", "| Page | Line | Detector | Confidence | Message |",
                "| --- | ---: | --- | ---: | --- |"]
        for f in review:
            out.append(
                f"| `{f.page}` | {f.line} | `{f.detector}` | "
                f"{f.confidence:.2f} | {_cell(f.message)} |"
            )

    by_detector = collections.Counter(f.detector for f in [*gated, *review])
    out += ["", "## By detector", "", "| Detector | Count |", "| --- | ---: |"]
    for name, n in by_detector.most_common():
        out.append(f"| `{name}` | {n} |")

    if stats.get("out_of_scope"):
        out += ["", f"> {stats['out_of_scope']} claim(s) were skipped as out of scope: "
                   "samples targeting a host other than the API under test."]
    if stats.get("abstentions"):
        out += ["", f"> {stats['abstentions']} claim(s) could not be adjudicated because "
                   "the spec declares no schema for that operation."]
    return "\n".join(out) + "\n"


def to_json(gated: list[Finding], review: list[Finding], stats: dict) -> str:
    return json.dumps(
        {
            "stats": stats,
            "findings": [f.to_dict() | {"severity": severity(f)} for f in gated],
            "review": [f.to_dict() | {"severity": severity(f)} for f in review],
        },
        indent=2,
    )


def to_sarif(gated: list[Finding], review: list[Finding], stats: dict) -> str:
    level = {"high": "error", "medium": "warning", "low": "note"}
    results = []
    for f in [*gated, *review]:
        results.append({
            "ruleId": f"freshness.{f.detector}",
            "level": level[severity(f)],
            "message": {"text": f.message},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": f.page},
                    "region": {"startLine": max(1, f.line)},
                }
            }],
        })
    detectors = sorted({f.detector for f in [*gated, *review]})
    return json.dumps({
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "docs-freshness",
                "informationUri": "https://github.com/weka-one/portfolio",
                "rules": [{"id": f"freshness.{d}", "name": d} for d in detectors],
            }},
            "results": results,
        }],
    }, indent=2)
