#!/usr/bin/env python3
"""Evaluation harness: precision, recall and F1 for the freshness checker.

Two evaluation sets, measuring different things, scored separately and never
averaged together:

  corpus   real pages, findings hand-adjudicated against eval/RUBRIC.md.
           Measures precision in the wild. Its recall figure is a lower bound,
           not a measurement: nobody read all 553 pages against the spec, so a
           defect the tool never reported is also a defect nobody labelled.

  mutated  clean pages with one known defect injected by eval/mutations.py.
           Measures recall exactly, because ground truth is constructed. Says
           nothing about precision -- every page is known-bad by design.

Reporting a single blended number across both would be meaningless, so the
harness refuses to produce one.

Baseline subtraction: a mutated page often carries pre-existing findings. Those
are computed from the unmutated page and then ignored -- neither credited nor
penalised -- so the score isolates the injected defect.

Usage:
    eval/harness.py                          # score every adjudicator arm
    eval/harness.py --adjudicator claude     # needs ANTHROPIC_API_KEY
    eval/harness.py --check-thresholds       # CI gate
    eval/harness.py --json results.json
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from freshness import llm  # noqa: E402
from freshness.detect import Detectors, default_bases  # noqa: E402
from freshness.extract import extract  # noqa: E402
from freshness.spec import Spec  # noqa: E402

CORPUS = ROOT.parent / "corpus" / "meilisearch-docs"
SPEC = ROOT.parent / "spec" / "meilisearch-openapi.json"
LABELS = HERE / "labels.jsonl"
MUTATIONS = HERE / "mutations.jsonl"
MUTATED = HERE / "mutated"
THRESHOLDS = HERE / "thresholds.json"


@dataclasses.dataclass
class Score:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def as_dict(self) -> dict:
        return {
            "tp": self.tp, "fp": self.fp, "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }

    def __iadd__(self, other: "Score") -> "Score":
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn
        return self


def confidence_curve(points: list[tuple[float, bool]], expected_total: int) -> list[dict]:
    """Precision and recall at each gate threshold.

    A single precision number hides the only decision that matters in practice:
    where to put the line between "fail the build" and "put this in a review
    queue". Sweeping it makes that a measurement rather than a preference.

    Recall here is over corpus expectations only; the independently-built probe
    and mutated figures are reported separately.
    """
    rows = []
    for threshold in (0.0, 0.35, 0.45, 0.6, 0.7, 0.8, 0.9):
        kept = [expected for conf, expected in points if conf >= threshold - 1e-9]
        tp = sum(1 for e in kept if e)
        fp = len(kept) - tp
        rows.append({
            "threshold": threshold,
            "reported": len(kept),
            "tp": tp,
            "fp": fp,
            "precision": round(tp / len(kept), 4) if kept else 0.0,
            "recall": round(tp / expected_total, 4) if expected_total else 0.0,
        })
    return rows


def load_jsonl(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class Runner:
    def __init__(self, spec: Spec, base_scoping: bool = True):
        self.spec = spec
        self.base_scoping = base_scoping
        self.texts = {
            str(p.relative_to(CORPUS)): p.read_text(encoding="utf-8")
            for p in sorted(CORPUS.rglob("*.mdx"))
        }
        # Base detection uses the whole corpus so one page's placeholder does
        # not skew what counts as "this API".
        all_claims = [c for page, text in self.texts.items() for c in extract(page, text)]
        self.bases = default_bases(spec, all_claims) if base_scoping else None

    def findings(self, page: str, text: str) -> list:
        return Detectors(self.spec, self.bases).run(extract(page, text))


# Arms. `naive` is an ablation, not a product configuration: it disables
# base-URL scoping to show what the tool scores without it.
ARMS = {
    "naive":     {"adjudicator": "none",      "base_scoping": False},
    "none":      {"adjudicator": "none",      "base_scoping": True},
    "heuristic": {"adjudicator": "heuristic", "base_scoping": True},
    "recorded":  {"adjudicator": "recorded",  "base_scoping": True},
    "claude":    {"adjudicator": "claude",    "base_scoping": True},
}


def evaluate(arm: str, cache: pathlib.Path | None = None) -> dict:
    config = ARMS[arm]
    spec = Spec.load(SPEC)
    runner = Runner(spec, base_scoping=config["base_scoping"])
    adjudicator = llm.build(config["adjudicator"], cache)

    labels = load_jsonl(LABELS)
    mutations = load_jsonl(MUTATIONS)

    per_detector: dict[str, Score] = collections.defaultdict(Score)
    corpus_score, mutated_score = Score(), Score()
    # Recall is scored per label source. `adjudicated` expectations were read
    # off this tool's own output, so their recall is 1.0 by construction and is
    # reported as circular rather than as a measurement. `probe` expectations
    # were built independently, by listing every inline `METHOD /path` and every
    # table-documented field in the corpus and checking each against the spec
    # by hand. Only probe and mutated recall mean anything.
    by_source: dict[str, Score] = collections.defaultdict(Score)
    # (confidence, was_expected) for every corpus finding, so the report can
    # sweep a gate threshold instead of asserting one.
    curve_points: list[tuple[float, bool]] = []
    expected_total = 0
    misses: list[str] = []
    false_alarms: list[str] = []
    ambiguous_tp = 0

    # --- corpus arm -------------------------------------------------------
    for record in labels:
        page = record["page"]
        text = runner.texts.get(page)
        if text is None:
            continue
        found = runner.findings(page, text)
        result = llm.apply(adjudicator, found, {page: text})
        produced = {(f.detector, f.evidence) for f in result["findings"]}

        expected_source = {(e["detector"], e["evidence"]): e.get("source", "adjudicated")
                           for e in record["expected"]}
        expected = set(expected_source)
        ambiguous = {(e["detector"], e["evidence"]) for e in record["expected"] if e.get("ambiguous")}

        confidence_of = {(f.detector, f.evidence): f.confidence for f in result["findings"]}
        expected_total += len(expected)
        for key, conf in confidence_of.items():
            curve_points.append((conf, key in expected))

        for key in sorted(produced & expected):
            corpus_score.tp += 1
            per_detector[key[0]].tp += 1
            by_source[expected_source[key]].tp += 1
            if key in ambiguous:
                ambiguous_tp += 1
        for key in sorted(produced - expected):
            corpus_score.fp += 1
            per_detector[key[0]].fp += 1
            by_source["|".join(record["sources"])].fp += 1
            false_alarms.append(f"{page}: {key[0]} {key[1]}")
        for key in sorted(expected - produced):
            corpus_score.fn += 1
            per_detector[key[0]].fn += 1
            by_source[expected_source[key]].fn += 1
            misses.append(f"{page}: {key[0]} {key[1]}")

    # --- mutated arm ------------------------------------------------------
    for mutation in mutations:
        page = mutation["page"]
        mutated_path = MUTATED / page
        if not mutated_path.exists():
            continue
        clean = runner.texts.get(page, "")
        baseline = {(f.detector, f.evidence) for f in runner.findings(page, clean)}

        text = mutated_path.read_text(encoding="utf-8")
        found = runner.findings(page, text)
        result = llm.apply(adjudicator, found, {page: text})
        produced = {(f.detector, f.evidence) for f in result["findings"]} - baseline

        wanted = mutation["detector"]
        if any(det == wanted for det, _ in produced):
            mutated_score.tp += 1
            per_detector[wanted].tp += 1
        else:
            mutated_score.fn += 1
            per_detector[wanted].fn += 1
            misses.append(f"{page}: [mutation {mutation['name']}] expected {wanted}")
        for det, ev in sorted(produced):
            if det != wanted:
                mutated_score.fp += 1
                per_detector[det].fp += 1
                false_alarms.append(f"{page}: [collateral] {det} {ev}")

    result = {
        "arm": arm,
        "corpus": corpus_score.as_dict(),
        "mutated": mutated_score.as_dict(),
        "per_detector": {k: v.as_dict() for k, v in sorted(per_detector.items())},
        "pages": {"corpus": len(labels), "mutated": len(mutations)},
        "by_source": {k: v.as_dict() for k, v in sorted(by_source.items())},
        "curve": confidence_curve(curve_points, expected_total),
        # The shipping gate (CLI default --min-confidence 0.6). This is what CI
        # asserts on: the numbers a user actually sees by default, not the
        # report-everything figures.
        "gated": next(r for r in confidence_curve(curve_points, expected_total)
                      if abs(r["threshold"] - 0.6) < 1e-9),
        "base_scoping": ARMS[arm]["base_scoping"],
        "ambiguous_true_positives": ambiguous_tp,
        "misses": sorted(misses),
        "false_alarms": sorted(false_alarms),
    }
    if isinstance(adjudicator, llm.RecordedAdjudicator):
        result["cache"] = {"hits": adjudicator.hits, "misses": adjudicator.misses}
    if isinstance(adjudicator, llm.ClaudeAdjudicator):
        result["api_calls"] = adjudicator.calls
    return result


def render(results: list[dict]) -> str:
    first = next((r for r in results if r["arm"] != "naive"), results[0])
    out = [
        "# Freshness checker evaluation", "",
        f"**{first['pages']['corpus']} hand-labelled corpus pages** and "
        f"**{first['pages']['mutated']} mutated pages** (one injected defect each).",
        "",
        "## Arms", "",
        "| Arm | Base scoping | Corpus precision | Probe recall | Mutated recall | FP | FN |",
        "| --- | :---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in results:
        c, m = r["corpus"], r["mutated"]
        probe = r["by_source"].get("probe", {"recall": 0.0})
        out.append(
            f"| `{r['arm']}` | {'yes' if r['base_scoping'] else 'no'} | {c['precision']:.2f} | "
            f"{probe['recall']:.2f} | {m['recall']:.2f} | {c['fp'] + m['fp']} | {c['fn'] + m['fn']} |"
        )
    out += [
        "",
        "`naive` is an ablation with base-URL scoping disabled. It is not a shipping",
        "configuration - it shows what the precision column costs without it.",
        "",
        "## Recall by label source", "",
        "| Source | TP | FN | Recall | Meaning |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    meaning = {
        "adjudicated": "**Circular.** Labelled from this tool's own output; recall here is 1.0 by construction and is not a measurement.",
        "probe": "Built independently of the tool, by checking every inline `METHOD /path` and table-documented field against the spec by hand. **This is the real recall number.**",
    }
    for name in ("adjudicated", "probe"):
        s_ = first["by_source"].get(name)
        if s_:
            out.append(f"| `{name}` | {s_['tp']} | {s_['fn']} | {s_['recall']:.2f} | {meaning[name]} |")
    mut = first["mutated"]
    out.append(
        f"| `mutated` | {mut['tp']} | {mut['fn']} | {mut['recall']:.2f} | "
        "Constructed ground truth; exact recall against drift of the kinds modelled in `mutations.py`. |"
    )

    out += ["", f"## Per detector (arm: `{first['arm']}`)", "",
            "| Detector | TP | FP | FN | Precision | Recall |",
            "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, s_ in first["per_detector"].items():
        out.append(
            f"| `{name}` | {s_['tp']} | {s_['fp']} | {s_['fn']} | "
            f"{s_['precision']:.2f} | {s_['recall']:.2f} |"
        )

    out += ["", f"## Gate threshold sweep (arm: `{first['arm']}`, corpus pages)", "",
            "| Min confidence | Reported | TP | FP | Precision | Recall |",
            "| ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in first["curve"]:
        out.append(
            f"| {row['threshold']:.2f} | {row['reported']} | {row['tp']} | {row['fp']} | "
            f"{row['precision']:.2f} | {row['recall']:.2f} |"
        )
    out += ["",
            "Findings below the gate are not discarded - they go to the review queue",
            "(`--min-confidence` on the CLI controls the gate, `--review` prints the rest)."]

    if first["misses"]:
        out += ["", "## Missed (false negatives)", ""]
        out += [f"- {m}" for m in first["misses"]]
    if first["false_alarms"]:
        out += ["", "## False positives", ""]
        out += [f"- {m}" for m in first["false_alarms"]]

    naive = next((r for r in results if r["arm"] == "naive"), None)
    if naive and naive["false_alarms"]:
        out += ["", "## What base-URL scoping prevents", "",
                f"The `naive` arm raises {len(naive['false_alarms'])} false positive(s) that "
                "scoping removes. A sample of them:", ""]
        out += [f"- {m}" for m in naive["false_alarms"][:8]]

    out += [
        "",
        f"> {first['ambiguous_true_positives']} true positive(s) are marked ambiguous: the spec",
        "> may be incomplete rather than the docs stale. Both need a human, so the",
        "> rubric counts them as actionable. Subtract them to recompute without.",
    ]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--adjudicator", action="append", dest="arms",
                    choices=list(ARMS))
    ap.add_argument("--cache", type=pathlib.Path)
    ap.add_argument("--json", type=pathlib.Path)
    ap.add_argument("--out-md", type=pathlib.Path)
    ap.add_argument("--check-thresholds", action="store_true")
    args = ap.parse_args()

    arms = args.arms or ["naive", "none", "heuristic"]
    results = [evaluate(arm, args.cache) for arm in arms]

    report = render(results)
    print(report)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2))
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(report)

    if args.check_thresholds:
        if not THRESHOLDS.exists():
            print("no thresholds committed; run with --json and commit eval/thresholds.json",
                  file=sys.stderr)
            return 1
        wanted = json.loads(THRESHOLDS.read_text())
        failures = []
        for r in results:
            limits = wanted.get(r["arm"])
            if not limits:
                continue
            for arm_name in ("corpus", "mutated", "gated", "probe"):
                for metric, floor in (limits.get(arm_name) or {}).items():
                    actual = (
                        r["by_source"]["probe"][metric]
                        if arm_name == "probe" else r[arm_name][metric]
                    )
                    if actual + 1e-9 < floor:
                        failures.append(
                            f"{r['arm']}/{arm_name}/{metric}: {actual:.3f} < {floor:.3f}"
                        )
        if failures:
            print("\nthreshold failures:", file=sys.stderr)
            for f in failures:
                print(f"  {f}", file=sys.stderr)
            return 1
        print("\nall committed thresholds met")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
