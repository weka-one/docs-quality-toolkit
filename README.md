# Documentation engineering portfolio

Three tools for keeping a developer-platform documentation set correct at scale,
all built and measured against a **real** 553-page documentation corpus and a
**real** OpenAPI 3.1 specification — neither of them written for these tools.

| | |
| --- | --- |
| [**docs-style-linter/**](docs-style-linter/) | 40 Vale rules, a structural linter, a composite GitHub Action, and the measurement to show whether they work. **1,092 → 704 alerts (−36%)**, with a proof that no code sample was modified. |
| [**docs-freshness/**](docs-freshness/) | Finds documentation that has drifted from the API it describes, plus an evaluation harness reporting precision and recall per detector. At its shipping gate: **precision 1.00, recall 0.76**. |
| [**docs-pipeline/**](docs-pipeline/) | Runs both of the above against docs that **do not live in Git** — a CMS API, an export, or the published site — on a schedule, and reports what changed since the last run. |

## Why the corpus is borrowed

A linter measured against documentation written by the author of that linter
always scores well, and the number means nothing. All three projects run against
[`meilisearch/documentation`](https://github.com/meilisearch/documentation)
(MIT, pinned at `7b72487`): 553 pages, 155,629 prose words, real API reference
tables, error-code listings, and multi-language code samples.

The freshness checker diffs against the official `meilisearch-openapi.json`
from the v1.54.0 release — a genuine machine-readable source of truth, not one
reconstructed from the documentation it is supposed to be checking.

Nothing proprietary to any employer is included. Every style rule cites a public
source (Google or Microsoft style guide, RFC 9110, WCAG 2.2).

## What each project is actually about

**The linter is about adoption, not rules.** Writing 40 patterns is an
afternoon. The work is in the parts that decide whether a team keeps it: a
fixture suite that catches rules Vale silently drops, a `changed-only` mode so
nobody meets the whole backlog on day one, scoping that took one parameter-table
rule from 157 alerts to 51 real ones, and a remediation pass that proves — on
every run — that it edited 16,541 protected segments zero times.

**The freshness checker is about knowing when to stay quiet.** It is used by
writers who did not build it. One confident false positive teaches them it is
noise; a miss costs one stale line. So it abstains when the spec is ambiguous,
counts its abstentions, splits output at a measured confidence gate, and ships
with an evaluation that reports its own circularity rather than quoting a
flattering number.

**The pipeline is about the docs that have no pull request.** The checks were
built assuming a Git checkout. A docs set whose system of record is a CMS has no
PR to gate and no merge base to diff against, so the layer that *produces* text
was replaced rather than the layer that checks it.

## Measured results

Style, over the full corpus, before and after the automated fixes:

| Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| Total alerts | 1,092 | 704 | −388 (−36%) |
| Alerts per 1,000 words | 7.02 | 4.53 | −2.49 |
| Files with at least one alert | 239 | 207 | −32 (−13%) |
| Errors | 347 | 247 | −100 (−29%) |
| Warnings | 509 | 266 | −243 (−48%) |

A separate structural pass over 294 pages found **475 issues, 132 of them
errors** — missing fence languages, malformed parameter tables, skipped heading
levels. These are invisible to a prose linter, which is why they are a separate
tool rather than more regexes.

Freshness, at the shipping gate (`--min-confidence 0.6`) over all 553 pages:
**73 findings** — 68 missing authorization, 3 unknown endpoints, 2 unknown
parameters. On the 26 hand-labelled evaluation pages the same configuration
reports 16 findings, **all of them true**, against 21 known defects.

The gate is the product decision, and the harness exists to make it visible:

| Min confidence | Reported | True | False | Precision | Recall |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00 (report everything) | 51 | 21 | 30 | 0.41 | 1.00 |
| 0.45 | 20 | 16 | 4 | 0.80 | 0.76 |
| **0.60 (shipping default)** | **16** | **16** | **0** | **1.00** | **0.76** |
| 0.70 | 5 | 5 | 0 | 1.00 | 0.24 |

## Both evaluations are built to be argued with

- Every style rule carries a `# Source:` and a `# Rationale:`, so a reviewer can
  argue with the rule rather than the regex.
- The linter's fixture suite has more negative cases (88) than positive (84),
  plus one documented false positive it has chosen to live with. A rule with no
  fixtures fails the build.
- The freshness evaluation's labelling rubric was written **before** the labels,
  every label carries a rationale, and corpus recall is reported as circular and
  excluded from the headline. The first version of that evaluation scored
  1.00/1.00, which is what prompted building an independent probe set — it
  initially scored 0.00.
- Coverage is documented as a limit, not a boast: of 40 checkable items in the
  source style guide, **23 are automated and 17 need a human**.
- All committed numbers are regenerated by `make`, and CI fails if they drift.

## Running them

```bash
cd docs-style-linter && make install-vale && make report
cd docs-freshness    && make install && make test && make eval
cd docs-pipeline     && make install && make test && make demo
```

CI: [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs all three test
suites, re-derives the metrics, and fails if the committed reports drift.
[`.github/workflows/docs-style.yml`](.github/workflows/docs-style.yml)
demonstrates the linter action on pull requests.

## When the docs are not in Git

The linter's GitHub Action assumes docs-as-code: a pull request to annotate and
a merge base to diff. That assumption does not survive a docs set whose system
of record is a CMS.

[`docs-pipeline/`](docs-pipeline/) replaces the delivery layer without touching
the checks. Four adapters cover the situations a docs team is actually in:

| Adapter | Use when |
| --- | --- |
| Filesystem | A directory, or an export the CMS produced |
| CMS API | The CMS has a read API, described by config rather than by code |
| Site crawl | It does not — read the published site |
| Rendered crawl | The site builds its pages in the browser |

The run is scheduled rather than triggered by a diff, and it fails on **new**
error-level findings rather than on the standing backlog, because a job that
fails every morning over work nobody has started is a job everyone mutes.

## Known limits

- **Recall rests on a small sample.** The only non-circular corpus recall figure
  comes from a 2-page probe set. Mutation-based recall (20 pages) measures drift
  *of the kinds modelled*, and says nothing about kinds that were not.
- **One corpus, one specification.** Everything was measured against Meilisearch.
  Precision on a documentation set with different conventions is unknown until it
  is run.
- **The −36% is what the automated fixes achieved**, not what the rules found.
  The remainder is deliberately left for a human; `COVERAGE.md` names which.
- **The LLM adjudication arm is off by default and every number here was
  measured without it.** `make eval-claude` fills that column in.
- **Rendered crawling is a capable fallback and a poor first choice.** It costs
  ~0.9s per page and breaks when a site is redesigned. It exists so a check can
  run before anyone has negotiated CMS access — the evidence it produces is best
  used to argue for an export or a read API.
