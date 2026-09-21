#!/usr/bin/env python3
"""Decide whether a Vale run should fail the job.

Split out from reporting on purpose. The report must always be produced --
a reviewer needs to see what changed even on a failing run -- while the gate is
the only step allowed to set a non-zero exit code.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

SEVERITIES = ("error", "warning", "suggestion")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("payload", type=pathlib.Path)
    ap.add_argument("--fail-on", default="error", choices=[*SEVERITIES, "never"])
    args = ap.parse_args()

    data = json.loads(args.payload.read_text() or "{}")
    alerts = [a for items in data.values() for a in items]

    if args.fail_on == "never":
        print(f"{len(alerts)} alert(s); gate disabled (fail-on=never).")
        return 0

    threshold = SEVERITIES.index(args.fail_on)
    blocking = [a for a in alerts if SEVERITIES.index(a.get("Severity", "warning")) <= threshold]
    if blocking:
        print(
            f"::error::{len(blocking)} style alert(s) at or above `{args.fail_on}`. "
            "See the annotations on the changed lines.",
            file=sys.stderr,
        )
        for alert in blocking[:10]:
            print(f"  {alert['Check']}: {alert.get('Message', '')}", file=sys.stderr)
        return 1

    print(f"{len(alerts)} alert(s), none at or above `{args.fail_on}`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
