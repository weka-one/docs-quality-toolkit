#!/usr/bin/env python3
"""Render a Markdown summary of Vale JSON for the GitHub job summary panel."""
from __future__ import annotations

import signal

# These write to stdout and are routinely piped into `head` during local use.
# Restoring the default SIGPIPE handler makes that exit cleanly instead of
# raising BrokenPipeError.
try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):  # not available on Windows
    pass

import collections
import json
import pathlib
import sys

SEVERITIES = ("error", "warning", "suggestion")


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit("usage: summarise.py <vale.json>")
    data = json.loads(pathlib.Path(sys.argv[1]).read_text() or "{}")

    by_rule: collections.Counter = collections.Counter()
    by_sev: collections.Counter = collections.Counter()
    by_file: collections.Counter = collections.Counter()
    links: dict[str, str] = {}
    for path, alerts in data.items():
        for alert in alerts:
            rule = alert["Check"]
            by_rule[rule] += 1
            by_sev[alert.get("Severity", "warning")] += 1
            by_file[path] += 1
            if alert.get("Link"):
                links.setdefault(rule, alert["Link"])

    total = sum(by_rule.values())
    if not total:
        print("No style alerts. :tada:")
        return 0

    parts = [f"**{by_sev[s]}** {s}{'s' if by_sev[s] != 1 else ''}" for s in SEVERITIES if by_sev[s]]
    print(f"{total} alert{'s' if total != 1 else ''} across {len(by_file)} file(s) — " + ", ".join(parts))
    print()
    print("| Rule | Count | Reference |")
    print("| --- | ---: | --- |")
    for rule, n in by_rule.most_common():
        ref = f"[source]({links[rule]})" if rule in links else "—"
        print(f"| `{rule}` | {n} | {ref} |")

    if len(by_file) > 1:
        print()
        print("<details><summary>Files with the most alerts</summary>")
        print()
        print("| File | Count |")
        print("| --- | ---: |")
        for path, n in by_file.most_common(15):
            print(f"| `{path}` | {n} |")
        print()
        print("</details>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
