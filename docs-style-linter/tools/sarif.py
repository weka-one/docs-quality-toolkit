#!/usr/bin/env python3
"""Convert Vale JSON into SARIF 2.1.0 for GitHub code scanning.

Vale has no SARIF writer, and its `--output=<template>` hook cannot see rule
metadata, so the conversion happens here instead. Doing it properly matters:
uploading SARIF with a populated `rules[]` array means a reviewer clicking an
annotation gets the rule's rationale and its source link, rather than a bare
regex match. That is the difference between a linter a team argues with and one
they switch off.

Severity mapping follows GitHub's convention -- SARIF has no "suggestion", so
Vale suggestions become SARIF notes, which surface without failing a check.

Usage:
    tools/sarif.py --target DIR --out vale.sarif
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import valelib  # noqa: E402

LEVEL = {"error": "error", "warning": "warning", "suggestion": "note"}
DEFAULT_STYLE_DIR = valelib.LINTER_ROOT / "styles" / "TikTokDocs"


def rule_catalog(style_dir: pathlib.Path = DEFAULT_STYLE_DIR) -> list[dict]:
    """Build SARIF `rules[]` from the rule files themselves.

    The `# Source:` and `# Rationale:` comments at the top of each rule are the
    reviewer-facing justification, so they are lifted into the SARIF help text.
    """
    rules = []
    for path in sorted(style_dir.glob("*.yml")):
        raw = path.read_text(encoding="utf-8")
        meta = yaml.safe_load(raw) or {}
        header = "\n".join(
            line.lstrip("# ").rstrip()
            for line in raw.splitlines()
            if line.startswith("#")
        ).strip()
        rule = {
            "id": f"TikTokDocs.{path.stem}",
            "name": path.stem,
            "shortDescription": {"text": str(meta.get("message", path.stem)).replace("%s", "…")},
            "fullDescription": {"text": header or path.stem},
            "defaultConfiguration": {"level": LEVEL.get(meta.get("level", "warning"), "warning")},
            "properties": {
                "tags": ["documentation", "style"],
                "extends": meta.get("extends", ""),
            },
        }
        if meta.get("link"):
            rule["helpUri"] = meta["link"]
            rule["help"] = {"text": f"{header}\n\nReference: {meta['link']}"}
        rules.append(rule)
    return rules


def build(
    target: pathlib.Path,
    repo_root: pathlib.Path,
    results_json: dict | None = None,
    style_dir: pathlib.Path = DEFAULT_STYLE_DIR,
) -> dict:
    if results_json is None:
        results_json = valelib.run_vale([str(target)])
    catalog = rule_catalog(style_dir)
    index = {r["id"]: i for i, r in enumerate(catalog)}

    results = []
    for path, alerts in results_json.items():
        abs_path = pathlib.Path(path).resolve()
        try:
            uri = str(abs_path.relative_to(repo_root))
        except ValueError:
            uri = abs_path.name
        for alert in alerts:
            rule_id = alert["Check"]
            start, end = alert.get("Span", [1, 1])[:2]
            result = {
                "ruleId": rule_id,
                "level": LEVEL.get(alert.get("Severity", "warning"), "warning"),
                "message": {"text": alert.get("Message", "")},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": uri},
                            "region": {
                                "startLine": max(1, alert.get("Line", 1)),
                                "startColumn": max(1, start),
                                "endColumn": max(1, end) + 1,
                                "snippet": {"text": alert.get("Match", "")},
                            },
                        }
                    }
                ],
            }
            if rule_id in index:
                result["ruleIndex"] = index[rule_id]
            results.append(result)

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Vale (TikTokDocs style package)",
                        "informationUri": "https://vale.sh",
                        "rules": catalog,
                    }
                },
                "results": results,
            }
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", type=pathlib.Path)
    ap.add_argument("--from-json", type=pathlib.Path,
                    help="use this Vale JSON instead of running Vale again")
    ap.add_argument("--styles", type=pathlib.Path, default=DEFAULT_STYLE_DIR)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path.cwd())
    args = ap.parse_args()

    if not args.target and not args.from_json:
        ap.error("pass --target or --from-json")
    results = json.loads(args.from_json.read_text() or "{}") if args.from_json else None
    sarif = build(
        args.target or pathlib.Path("."), args.repo_root.resolve(), results, args.styles
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(sarif, indent=2))
    n = len(sarif["runs"][0]["results"])
    print(f"wrote {args.out} ({n} results, {len(sarif['runs'][0]['tool']['driver']['rules'])} rules)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
