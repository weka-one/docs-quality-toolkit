# Evaluation

A freshness checker that reports drift nobody can act on is worse than no
checker: it trains writers to ignore a channel you later need. So the question
this evaluation answers is not "how many findings", it is **what fraction of
what we report is worth someone's time, and what fraction of real drift do we
miss**.

## Three label sources, scored separately

| Source | Pages | Built how | Measures |
| --- | ---: | --- | --- |
| `adjudicated` | 9 | Read the tool's output, judged each finding against [RUBRIC.md](RUBRIC.md) | Precision |
| `probe` | 2 | Built **without** the tool: listed every inline `` `METHOD /path` `` and every table-documented field in all 553 pages, checked each against the spec by hand | Recall (the only non-circular corpus figure) |
| `control` | 16 | Pages an earlier version got wrong, plus clean pages with real claims | Precision, specifically against known traps |
| `mutated` | 20 | `mutations.py` injects one known defect per page | Recall, exactly |

They are never averaged. Blending a circular recall figure with a constructed
one produces a number that means nothing.

### Why `adjudicated` recall is reported as circular

Those labels were written by reading what the tool produced. Its recall on them
is 1.0 by construction, and the harness says so in the output rather than
quoting it as a result. The `probe` set exists specifically to break that
circularity — and when it was first built, the tool scored **0.00** on it.

### Why mutation is necessary

Measuring recall on real pages means reading all 553 against a 72-path spec by
hand. Mutation constructs ground truth instead: each mutation is the textual
form of a change that really happens to an API — a parameter renamed, a verb
changed, a route moved, an enum value retired, credentials dropped from a
sample.

Its limit, stated plainly: mutations measure recall against drift **of the
kinds modelled in `mutations.py`**. They say nothing about drift nobody thought
to model. That is exactly what `probe` is for.

Baseline subtraction: mutated pages often carry pre-existing findings. Those
are computed from the clean page and then ignored — neither credited nor
penalised — so the score isolates the injected defect.

## What the evaluation changed

It was not a scoreboard. Every number below moved because the harness found a
defect:

1. **Base-URL scoping.** The first run reported `GET /meilisearch/meilisearch/latest/config.toml`
   as missing from the spec. True, and useless — that is a GitHub download. Once
   the extractor kept the sample's base URL and the detectors ignored calls to
   other services, corpus precision went from **0.35 to 1.00**. The `naive` arm
   keeps that ablation runnable.

2. **A recall blind spot worth more than the precision fix.** The `probe` set
   scored **0.00**: `events_endpoint.mdx` is a complete reference page for
   `POST /events` — a route marker and an eight-field body table — for a route
   absent from the spec, and the curl-only extractor saw none of it. Adding
   inline-code and JSX route extraction took probe recall to **1.00**.

3. **That fix cost precision, and the gate is the answer.** Prose route mentions
   carry no base URL, and a migration guide names Elasticsearch's routes in
   identical syntax. Reporting everything drops precision to 0.41. Rather than
   pick between them, those claims are emitted at low confidence and the report
   splits at a gate:

   | Min confidence | Reported | Precision | Recall |
   | ---: | ---: | ---: | ---: |
   | 0.00 | 51 | 0.41 | 1.00 |
   | 0.45 | 20 | 0.80 | 0.76 |
   | **0.60** | **16** | **1.00** | **0.76** |
   | 0.90 | 3 | 1.00 | 0.14 |

   0.60 is the CLI default. Below it is a review queue, not a discard.

4. **The obvious non-LLM baseline adds nothing.** `HeuristicAdjudicator` was
   written to keep the LLM honest — it is easy to show a model improves a
   metric, harder to show it beats the rules someone would write in an
   afternoon. Once base scoping existed, the heuristic scored **identically to
   no adjudicator at all**. Its one real lever (the sample's host) was already
   handled upstream, and the signal it would need for the remaining cases — is
   this page documenting somebody else's API? — lives in surrounding prose.

   An earlier version did read that prose, and a unit test caught it dismissing
   true findings because the page happened to link to GitHub. Findings now carry
   their own provenance and the heuristic judges the sample, not the page.

## The LLM arm is implemented and unmeasured

`ClaudeAdjudicator` is complete and wired into the harness. It has not been run,
because this environment has no Anthropic credentials — so no numbers for it are
quoted anywhere. Reporting an ablation that was never executed would be worse
than leaving the column empty.

To fill it in:

```bash
export ANTHROPIC_API_KEY=...
make eval-claude
```

That records every verdict to `eval/llm_cache.json`. Afterwards the `recorded`
arm replays those verdicts offline, so CI and the committed numbers stay
reproducible and byte-identical without a key. An evaluation whose score moves
when an external service is retrained is not a regression test.

The hypothesis it would test is stated in advance, so the result can disagree:
the remaining 30 false positives are prose route mentions whose resolution
depends on whether the page documents this API or another one — a judgement from
surrounding context, which is the one thing neither the index nor the heuristic
can do.

## Bias

The same person wrote the detectors and the labels. The mitigations are
structural, not assurances:

- [RUBRIC.md](RUBRIC.md) was written before the labels and states what counts.
- The `probe` set was built from the corpus and the spec without consulting tool
  output, which is why it could score 0.00.
- Every label carries a `rationale`, so a reader can disagree with a specific
  one.
- Ambiguous cases (spec possibly incomplete rather than docs stale) are flagged
  and counted separately, so the scores can be recomputed without them.

## Reproducing

```bash
make mutate   # regenerate seeded drift (seeded; deterministic)
make eval     # score every offline arm
make thresholds
```
