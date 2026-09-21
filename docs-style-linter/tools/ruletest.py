#!/usr/bin/env python3
"""Fixture runner for the TikTokDocs Vale package.

Materialises every snippet in tests/rules.yml as its own .mdx file, runs Vale
once over the resulting directory, and asserts that each rule fired exactly
where it was supposed to.

Isolating snippets into separate files matters: `Acronyms` is a page-scoped
conditional check and heading rules only see `scope: heading`, so snippets
sharing a file would contaminate each other.

Exit code is 1 if any case fails, which is what CI keys on.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

import yaml

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
FIXTURES = ROOT / "tests" / "rules.yml"
CONFIG = ROOT / ".vale.ini"


def vale_bin() -> str:
    found = shutil.which("vale")
    if found:
        return found
    fallback = pathlib.Path.home() / "go" / "bin" / "vale"
    if fallback.exists():
        return str(fallback)
    sys.exit("vale not found on PATH. See docs-style-linter/README.md for install steps.")


def preflight() -> list[str]:
    """Catch rule files that Vale would silently skip.

    Vale drops a rule whose YAML does not type-check, without saying so — the
    rule simply stops firing. The worst offender is YAML 1.1 keyword coercion:
    an unquoted `NULL`, `TRUE`, `FALSE`, `NO`, `ON`, `OFF` or `YES` in an
    exception list parses as null or a boolean, and takes the whole rule down
    with it. This suite found exactly that bug in `Acronyms`, so the check now
    runs before every fixture pass.
    """
    problems = []
    for path in sorted((ROOT / "styles" / "TikTokDocs").glob("*.yml")):
        try:
            rule = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            problems.append(f"{path.name}: unparseable YAML ({exc})")
            continue
        if not isinstance(rule, dict):
            problems.append(f"{path.name}: top level is not a mapping")
            continue
        if "extends" not in rule:
            problems.append(f"{path.name}: missing `extends`")
        if rule.get("level") not in {"suggestion", "warning", "error"}:
            problems.append(f"{path.name}: level {rule.get('level')!r} is not valid")
        for key in ("exceptions", "tokens"):
            for item in rule.get(key) or []:
                if not isinstance(item, str):
                    problems.append(
                        f"{path.name}: `{key}` entry {item!r} parsed as "
                        f"{type(item).__name__}, not str — quote it"
                    )
        for key, val in (rule.get("swap") or {}).items():
            if not isinstance(key, str) or not isinstance(val, str):
                problems.append(f"{path.name}: `swap` entry {key!r}: {val!r} is not string to string")
    return problems


def slug(rule: str) -> str:
    return rule.split(".", 1)[-1]


def build_cases(spec: dict) -> list[dict]:
    cases = []
    for rule, groups in spec.items():
        for kind in ("bad", "good", "known_fp"):
            for idx, entry in enumerate(groups.get(kind) or []):
                # `known_fp` entries carry a `why`; bad/good are bare strings.
                text = entry["text"] if isinstance(entry, dict) else entry
                why = entry.get("why", "") if isinstance(entry, dict) else ""
                cases.append(
                    {
                        "rule": rule,
                        "kind": kind,
                        "text": text,
                        "why": why,
                        "name": f"{slug(rule)}__{kind}__{idx}.mdx",
                    }
                )
    return cases


def run_vale(workdir: pathlib.Path) -> dict:
    proc = subprocess.run(
        [vale_bin(), f"--config={CONFIG}", "--output=JSON", "--no-exit", str(workdir)],
        capture_output=True,
        text=True,
    )
    if not proc.stdout.strip():
        if proc.returncode != 0:
            sys.exit(f"vale failed:\n{proc.stderr}")
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.exit(f"vale produced non-JSON output:\n{proc.stdout[:2000]}\n{proc.stderr}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule", help="run only cases for this rule (substring match)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    problems = preflight()
    if problems:
        print("rule package failed preflight:\n")
        for problem in problems:
            print(f"  {problem}")
        return 1

    spec = yaml.safe_load(FIXTURES.read_text())
    cases = build_cases(spec)
    if args.rule:
        cases = [c for c in cases if args.rule.lower() in c["rule"].lower()]
        if not cases:
            sys.exit(f"no fixtures match {args.rule!r}")

    with tempfile.TemporaryDirectory() as tmp:
        workdir = pathlib.Path(tmp) / "fixtures"
        workdir.mkdir()
        for case in cases:
            # Frontmatter mirrors the corpus so BlockIgnores behaves identically.
            body = case["text"]
            (workdir / case["name"]).write_text(
                f"---\ntitle: fixture\n---\n\n{body}\n", encoding="utf-8"
            )
        results = run_vale(workdir)

    fired: dict[str, set[str]] = {}
    for path, alerts in results.items():
        name = pathlib.Path(path).name
        fired[name] = {a["Check"] for a in alerts}

    # Every rule in the package must have at least one fixture. Without this,
    # adding a rule and forgetting to test it looks identical to a passing run.
    packaged = {f"TikTokDocs.{p.stem}" for p in (ROOT / "styles" / "TikTokDocs").glob("*.yml")}
    untested = packaged - set(spec)
    if untested and not args.rule:
        print(f"rules with no fixtures: {', '.join(sorted(untested))}\n")
        return 1

    failures = []
    for case in cases:
        hits = fired.get(case["name"], set())
        did_fire = case["rule"] in hits
        want = case["kind"] in ("bad", "known_fp")
        ok = did_fire == want
        if args.verbose or not ok:
            mark = "ok  " if ok else "FAIL"
            print(f"{mark} {case['rule']:<38} {case['kind']}: {case['text'][:66]}")
        if not ok:
            if case["kind"] == "known_fp":
                detail = (
                    "documented false positive no longer fires - the rule improved, "
                    "so move this case to `good`"
                )
            elif want:
                detail = "expected an alert, got none"
            else:
                detail = f"expected silence, got {sorted(hits)}"
            failures.append((case, detail))

    print()
    if failures:
        print(f"{len(failures)} of {len(cases)} cases failed:\n")
        for case, detail in failures:
            print(f"  {case['rule']} [{case['kind']}] {detail}")
            print(f"    {case['text'][:100]}")
        return 1

    rules = len({c["rule"] for c in cases})
    n_fp = sum(1 for c in cases if c["kind"] == "known_fp")
    print(f"all {len(cases)} cases passed across {rules} rules")
    if n_fp:
        print(f"({n_fp} documented false positive(s) - see `known_fp` in tests/rules.yml)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
