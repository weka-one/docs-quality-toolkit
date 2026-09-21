#!/usr/bin/env python3
"""Emit GitHub workflow annotations from Vale JSON.

Annotations put each alert on the diff line it belongs to. Without them a
reviewer has to open the job log, match line numbers by hand, and decide
whether the linter is talking about code they wrote -- which is enough friction
that the check gets ignored.

GitHub caps annotations at 10 per step for each level, so output is ordered by
severity: errors are the ones that block, and they must not be crowded out by
suggestions.
"""
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
import os
import pathlib
import sys

ANNOTATION = {"error": "error", "warning": "warning", "suggestion": "notice"}
LIMIT = int(os.environ.get("VALE_ANNOTATION_LIMIT", "50"))
ORDER = {"error": 0, "warning": 1, "suggestion": 2}


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit("usage: annotate.py <vale.json>")
    payload = pathlib.Path(sys.argv[1])
    data = json.loads(payload.read_text() or "{}")

    alerts = []
    for path, items in data.items():
        for item in items:
            alerts.append((path, item))
    alerts.sort(key=lambda pair: (ORDER.get(pair[1].get("Severity", "warning"), 3), pair[0], pair[1].get("Line", 0)))

    shown: collections.Counter = collections.Counter()
    for path, alert in alerts:
        severity = alert.get("Severity", "warning")
        if shown[severity] >= LIMIT:
            continue
        shown[severity] += 1
        kind = ANNOTATION.get(severity, "warning")
        line = max(1, alert.get("Line", 1))
        col, end = (alert.get("Span") or [1, 1])[:2]
        # Newlines would terminate the workflow command early.
        message = alert.get("Message", "").replace("\n", " ").replace("%", "%25")
        title = alert.get("Check", "Vale")
        print(
            f"::{kind} file={path},line={line},col={max(1, col)},"
            f"endColumn={max(1, end) + 1},title={title}::{message}"
        )

    suppressed = len(alerts) - sum(shown.values())
    if suppressed > 0:
        print(f"::notice::{suppressed} further alert(s) not annotated; see the job summary for full counts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
