#!/usr/bin/env python3
"""Scheduled documentation monitor.

Pull the current content from wherever it lives, run every check over it,
record a snapshot, and report what changed since the last run.

This replaces the pull-request gate, which does not apply when the CMS is the
system of record. GitHub Actions is still the runner — it just runs on a cron
against the CMS instead of on a diff.

The reporting bias follows from that. A gate blocks the change in front of it;
a monitor watches a corpus that already has a backlog. Failing the run on the
backlog trains everyone to ignore it, so the run fails on **new** error-level
findings and reports the standing total separately.

    pipeline/run.py --config config.demo.yml
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))

from pipeline import sources  # noqa: E402

STYLE_TOOLS = REPO / "docs-style-linter" / "tools"
FRESHNESS = REPO / "docs-freshness"


def _run(argv: list[str], cwd: pathlib.Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=cwd)
    return proc.returncode, proc.stdout, proc.stderr


def run_style(staged: pathlib.Path, config: dict) -> list[dict]:
    """Vale, via the existing linter package."""
    vale_config = (ROOT / config["vale_config"]).resolve()
    code, out, err = _run([
        sys.executable, str(STYLE_TOOLS / "report.py"),
        "--target", str(staged), "--out-json", str(staged.parent / "style.json"),
    ])
    payload = staged.parent / "style.json"
    if not payload.exists():
        print(f"  style check produced no output ({err.strip()[:200]})", file=sys.stderr)
        return []
    data = json.loads(payload.read_text())
    before = data.get("before") or {}
    return [
        {"check": rule, "count": n, "kind": "style"}
        for rule, n in (before.get("by_rule") or {}).items()
    ]


def run_style_findings(staged: pathlib.Path, vale_config: pathlib.Path) -> list[dict]:
    """Per-finding style output, which is what a writer acts on."""
    sys.path.insert(0, str(STYLE_TOOLS))
    import valelib  # noqa: E402

    results = valelib.run_vale([str(staged)], config=vale_config)
    findings = []
    for path, alerts in results.items():
        rel = pathlib.Path(path)
        try:
            rel = rel.resolve().relative_to(staged.resolve())
        except ValueError:
            rel = pathlib.Path(rel.name)
        for alert in alerts:
            findings.append({
                "kind": "style",
                "check": alert["Check"].split(".", 1)[-1],
                "page": str(rel),
                "line": alert.get("Line", 1),
                "level": alert.get("Severity", "warning"),
                "message": alert.get("Message", ""),
            })
    return findings


def run_structure(staged: pathlib.Path, policy: pathlib.Path) -> list[dict]:
    out = staged.parent / "structure.json"
    _run([
        sys.executable, str(STYLE_TOOLS / "structure_lint.py"), str(staged),
        "--config", str(policy), "--format", "json", "--out", str(out),
    ])
    if not out.exists():
        return []
    data = json.loads(out.read_text())
    return [
        {"kind": "structure", "check": i["check"], "page": i["page"],
         "line": i["line"], "level": i["level"], "message": i["message"]}
        for i in data.get("issues", [])
    ]


def run_freshness(staged: pathlib.Path, config: dict) -> list[dict]:
    spec = (ROOT / config["spec"]).resolve()
    if not spec.exists():
        print(f"  freshness: spec not found at {spec}", file=sys.stderr)
        return []
    out = staged.parent / "freshness.json"
    code, _, err = _run([
        sys.executable, "-m", "freshness",
        "--docs", str(staged), "--spec", str(spec),
        "--min-confidence", str(config.get("min_confidence", 0.6)),
        "--format", "json", "--out", str(out),
    ], cwd=FRESHNESS)
    if not out.exists():
        print(f"  freshness check produced no output ({err.strip()[:200]})", file=sys.stderr)
        return []
    data = json.loads(out.read_text())
    findings = []
    for group, gated in (("findings", True), ("review", False)):
        for f in data.get(group, []):
            findings.append({
                "kind": "freshness",
                "check": f["detector"],
                "page": f["page"],
                "line": f["line"],
                "level": "error" if gated and f["confidence"] >= 0.8 else
                         ("warning" if gated else "suggestion"),
                "message": f["message"],
            })
    return findings


def snapshot(findings: list[dict], pages: int, source_name: str) -> dict:
    import collections

    by_level = collections.Counter(f["level"] for f in findings)
    by_kind = collections.Counter(f["kind"] for f in findings)
    by_check = collections.Counter(f["check"] for f in findings)
    return {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": source_name,
        "pages": pages,
        "total": len(findings),
        "by_level": dict(sorted(by_level.items())),
        "by_kind": dict(sorted(by_kind.items())),
        "by_check": dict(sorted(by_check.items(), key=lambda kv: (-kv[1], kv[0]))),
        # Identity of a finding, for diffing runs. Line numbers move when a page
        # is edited, so they are deliberately excluded: a reworded paragraph
        # should not read as a fixed finding plus a new one.
        "fingerprints": sorted({f"{f['kind']}:{f['check']}:{f['page']}" for f in findings}),
        "findings": sorted(findings, key=lambda f: (f["page"], f["line"], f["check"])),
    }


def load_previous(history: pathlib.Path) -> dict | None:
    runs = sorted(history.glob("*.json"))
    return json.loads(runs[-1].read_text()) if runs else None


def diff(current: dict, previous: dict | None) -> dict:
    if not previous:
        return {"new": [], "fixed": [], "first_run": True}
    now, before = set(current["fingerprints"]), set(previous["fingerprints"])
    return {
        "new": sorted(now - before),
        "fixed": sorted(before - now),
        "first_run": False,
        "previous_timestamp": previous["timestamp"],
        "total_delta": current["total"] - previous["total"],
    }


def main() -> int:
    import yaml

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=pathlib.Path, default=ROOT / "config.demo.yml")
    ap.add_argument("--keep-staging", action="store_true", help="leave the staged tree on disk")
    ap.add_argument("--no-record", action="store_true", help="do not write a history snapshot")
    ap.add_argument("--source-root", type=pathlib.Path,
                    help="override a filesystem source's root (for comparing two content states)")
    ap.add_argument("--label", help="label recorded with this run, shown on the dashboard")
    args = ap.parse_args()

    config = yaml.safe_load(args.config.read_text())
    report_dir = ROOT / config["report"]["out"]
    history_dir = ROOT / config["report"]["history"]
    report_dir.mkdir(parents=True, exist_ok=True)
    history_dir.mkdir(parents=True, exist_ok=True)

    source_config = dict(config["source"])
    if args.source_root:
        source_config["type"] = "filesystem"
        source_config["root"] = str(args.source_root)
    if source_config.get("type") == "filesystem":
        source_config["root"] = str((ROOT / source_config["root"]).resolve())
    source = sources.build(source_config)

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="docs-pipeline-"))
    staged = tmp / "content"
    print(f"==> Pulling content from {source.name}")
    try:
        sources.materialise(source, staged)
    except sources.SourceError as exc:
        print(f"\nCould not fetch the documentation.\n\n{exc}\n", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"\nCould not fetch the documentation.\n  {type(exc).__name__}: {exc}\n",
              file=sys.stderr)
        return 1
    pages = len([p for p in staged.rglob("*.md")] + [p for p in staged.rglob("*.mdx")])
    print(f"    {pages} pages staged")

    findings: list[dict] = []
    checks = config["checks"]
    if checks.get("style", {}).get("enabled", True):
        print("==> Style")
        findings += run_style_findings(staged, (ROOT / checks["style"]["vale_config"]).resolve())
    if checks.get("structure", {}).get("enabled", True):
        print("==> Structure")
        findings += run_structure(staged, (ROOT / checks["structure"]["policy"]).resolve())
    if checks.get("freshness", {}).get("enabled", True):
        print("==> Freshness")
        findings += run_freshness(staged, checks["freshness"])

    current = snapshot(findings, pages, source.name)
    current["label"] = args.label or ""
    previous = load_previous(history_dir)
    delta = diff(current, previous)
    current["delta"] = delta

    if not args.no_record:
        stamp = current["timestamp"].replace(":", "").replace("-", "")
        (history_dir / f"{stamp}.json").write_text(json.dumps(current, indent=2))
    (report_dir / "latest.json").write_text(json.dumps(current, indent=2))

    print(f"\n{current['total']} finding(s) across {pages} pages")
    for level in ("error", "warning", "suggestion"):
        if current["by_level"].get(level):
            print(f"  {level}: {current['by_level'][level]}")
    if delta["first_run"]:
        print("\nFirst run: no baseline to compare against.")
    else:
        print(f"\nSince {delta['previous_timestamp']}: "
              f"{len(delta['new'])} new, {len(delta['fixed'])} fixed "
              f"({delta['total_delta']:+d} overall)")

    if not args.keep_staging:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"\nstaged tree kept at {staged}")

    # Fail on regressions, never on the standing backlog.
    threshold = config["report"].get("fail_on_new_errors")
    if threshold and not delta["first_run"]:
        errors_by_fp = {f"{f['kind']}:{f['check']}:{f['page']}" for f in findings if f["level"] == "error"}
        new_errors = [fp for fp in delta["new"] if fp in errors_by_fp]
        if len(new_errors) >= threshold:
            print(f"\n{len(new_errors)} new error-level finding(s):", file=sys.stderr)
            for fp in new_errors[:15]:
                print(f"  {fp}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
