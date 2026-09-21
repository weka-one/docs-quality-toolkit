# Documentation freshness checker

Finds documentation that has drifted from the API it describes, by checking
every claim a page makes against an OpenAPI specification — and ships with an
evaluation harness that says how often it is right.

Run against a real 553-page corpus and a real OpenAPI 3.1 spec, neither of them
written for this tool.

## What it found

Genuine defects in published documentation, not seeded ones:

| Page | Finding |
| --- | --- |
| `federated_search.mdx` | Three samples `POST` a dataset to `/indexes/{name}`. That route accepts `GET`, `PATCH` and `DELETE` only — documents go to `/indexes/{name}/documents`. Every reader who copies it gets a 405. |
| `code_samples_webhooks_patch_1.mdx` | Body field `header`; the API takes `headers`. The singular is ignored silently, so the sample looks like it works. This is a *generated* sample, so the defect ships to every SDK language. |
| `code_samples_joins_delete_orphaned_1.mdx` | `POST /indexes/deals/delete-by-filter` — no such route. |
| `bind_events_to_user.mdx` | Sends `/events` to `MEILISEARCH_URL`, while the generated snippet for the same endpoint uses `https://PROJECT_URL`. The docs contradict each other about which service hosts it. |
| `performance_tuning.mdx` | Eleven complete `curl` samples against secured endpoints; the page never mentions `Authorization`. All eleven 401. |
| `events_endpoint.mdx` | A full reference page — route marker plus an eight-field body table — for a route absent from the spec entirely. |

## Results

From [`eval/`](eval/), regenerate with `make eval`:

| Arm | Corpus precision | Probe recall | Mutated recall |
| --- | ---: | ---: | ---: |
| `naive` (no base scoping) | 0.35 | 1.00 | 1.00 |
| `none` (shipping, report everything) | 0.41 | 1.00 | 1.00 |
| `none` **at the default gate (0.6)** | **1.00** | — | — |

46 labelled pages: 26 hand-labelled real pages and 20 with seeded drift.
`probe` is the only non-circular recall figure — see below.

## How it works

```
spec.py      index an OpenAPI document: $ref resolution, allOf/oneOf
             composition, path templating, enums keyed by field
extract.py   docs -> falsifiable claims (curl samples, inline routes,
             JSX route markers, parameter tables)
detect.py    claims x spec -> findings, with confidence and provenance
llm.py       optional adjudication of the uncertain ones
report.py    Markdown, JSON, or SARIF
cli.py       python -m freshness
```

Only claims that can be **falsified** are extracted. Prose describing what a
parameter means is not a claim — nothing in the spec can contradict it without
a judgement call.

### Detectors

| Detector | Question |
| --- | --- |
| `unknown_endpoint` | Does this method+path exist? |
| `unknown_parameter` | Does this operation accept this body field or query parameter? |
| `unknown_enum_value` | Is this value in the field's enum? |
| `missing_auth` | Does a secured operation's sample send credentials? |
| `deprecated_endpoint` | Is the operation deprecated without the page saying so? |

### The bias that shaped every one of them

Precision over recall. This tool is used by writers who did not build it. One
confident false positive teaches them it is noise and they stop reading its
output; a miss costs one stale line nobody was looking at. So detectors abstain
when the spec is ambiguous — an operation with no declared body schema produces
silence, not a guess — and abstentions are counted and reported rather than
hidden.

## Two tiers, not one list

```bash
python -m freshness --docs ./docs --spec ./openapi.json
# 73 finding(s) at or above the gate (confidence >= 0.6), 40 queued for review
```

The harness measures where the gate belongs rather than asserting it:

| Min confidence | Reported | Precision | Recall |
| ---: | ---: | ---: | ---: |
| 0.00 | 51 | 0.41 | 1.00 |
| 0.45 | 20 | 0.80 | 0.76 |
| **0.60** | **16** | **1.00** | **0.76** |
| 0.90 | 3 | 1.00 | 0.14 |

A checker that fails the build on its low-confidence output gets switched off in
a week. One that silently drops it misses real drift. The gate is how you get
both: below it is a review queue, not a discard.

## Base-URL scoping

A documentation corpus calls more than one service, and every URL reduces to a
plausible-looking path once the host is stripped. The first run of this tool
reported:

> `GET /meilisearch/meilisearch/latest/config.toml` does not appear in the spec

True, and completely useless — that is a GitHub download. Claims now carry the
base URL they targeted, and anything aimed elsewhere is skipped and counted.
Corpus precision: **0.35 → 1.00**. The `naive` evaluation arm keeps the
ablation runnable so the claim stays checkable.

```bash
python -m freshness --docs ./docs --spec ./openapi.json --suggest-bases
```

prints every base found in the corpus, so the decision is visible rather than
magic. Override with `--base` (repeatable).

## LLM adjudication

The deterministic detectors answer *does the spec contain this?* — a lookup, at
which an index is faster, cheaper and exactly correct. They cannot answer *does
this disagreement matter?*, and that is where trust is won or lost.

So the model is scoped narrowly: it never searches for drift, and it only sees
findings the detectors already marked uncertain. Four backends implement one
protocol so the harness can ablate between them:

| Backend | Purpose |
| --- | --- |
| `none` | Deterministic baseline |
| `heuristic` | Hand-written rules — the bar the model must beat to justify its cost |
| `claude` | Messages API, structured output, writes a replay cache |
| `recorded` | Replays that cache, so CI is offline and reproducible |

**The `claude` arm is implemented but has not been run** — this environment has
no Anthropic credentials, so no numbers are quoted for it anywhere. Reporting an
ablation that never executed is worse than an empty column. `make eval-claude`
fills it in.

The measured result for the non-LLM baseline is a negative one, reported as
such: once base scoping existed, `heuristic` scored **identically to no
adjudicator**. Its only real lever was the sample's host, already handled
upstream.

## Evaluation

Full methodology in [`eval/README.md`](eval/README.md); labelling rules, fixed
before the labels, in [`eval/RUBRIC.md`](eval/RUBRIC.md).

The part worth reading: corpus **recall is reported as circular and excluded**.
Those labels were written by reading the tool's own output, so its recall on
them is 1.0 by construction. Recall is measured on two sets built independently
— `probe`, assembled by hand from the corpus and spec without consulting tool
output, and `mutated`, where ground truth is constructed. When `probe` was first
built, the tool scored **0.00** on it.

## Commands

```
make install      dependencies
make test         55 unit tests
make check        run over the corpus at the default gate
make review       show only the review queue
make mutate       regenerate seeded drift (deterministic)
make eval         score every offline arm
make eval-claude  score the LLM arm (needs ANTHROPIC_API_KEY)
make thresholds   CI gate on committed floors
```

Output formats: `--format markdown|json|sarif`. SARIF uploads to GitHub code
scanning, so drift lands on the pull request that caused it.

## Requirements

Python 3.11+, PyYAML, pytest. `anthropic` only for the `claude` arm.
