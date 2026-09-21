# Documentation style linter

A Vale rule package, a composite GitHub Action, and the measurement tooling to
show whether either is working — run against a real 553-page documentation
corpus.

## Results

Measured on [`corpus/meilisearch-docs`](../corpus/) (553 pages, 155,629 prose
words), regenerate with `make report`:

| Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| Total alerts | 589 | 364 | **−38%** |
| Alerts per 1,000 words | 3.78 | 2.34 | −1.44 |
| Error-level alerts | 83 | 7 | **−92%** |
| Files with at least one alert | 177 | 142 | −20% |

"After" is the corpus with `tools/remediate.py` applied: 228 deterministic
fixes across 97 files. Full per-rule and per-area breakdown in
[`reports/before-after.md`](reports/before-after.md).

The numbers come from re-running Vale over the remediated tree, not from
counting fixes applied. Those differ whenever a fix creates or masks another
violation, and only the re-run tells you which happened.

## What is actually here

```
.vale.ini                  Vale config (MDX-aware)
styles/TikTokDocs/         22 rules
styles/vocabulary/         accepted terms -> per-rule exceptions
action.yml                 composite GitHub Action
tools/ruletest.py          fixture suite + rule-package preflight
tools/remediate.py         deterministic fixes for the automatable subset
tools/verify_codeblocks.py proves remediation never edits a code sample
tools/report.py            before/after content-quality metrics
tools/sarif.py             SARIF 2.1.0 for GitHub code scanning
tools/sync_vocab.py        compiles the vocabulary into rule exceptions
tests/rules.yml            103 fixture cases
```

## The rules

22 rules in five groups. Every rule file opens with a `# Source:` citing a
public style guide or RFC and a `# Rationale:` explaining why the rule exists,
because a reviewer should be able to argue with the rule rather than with a
regex.

| Group | Rules |
| --- | --- |
| Voice and tone | `Filler` `Please` `FirstPerson` `Hedging` `NoteThat` |
| Word choice | `Wordiness` `AllowsYouTo` `LatinAbbreviations` `UIActions` `InclusiveLanguage` `GenderNeutral` |
| Terminology | `Terminology` `ApiKeyCase` `Acronyms` |
| Structure | `HeadingSentenceCase` `HeadingPunctuation` `LinkText` `SentenceLength` |
| API reference | `HTTPMethodCase` `EndpointInCode` `StatusCodeName` `CurlyQuotes` |

The rule set was chosen from measured corpus frequencies rather than picked
from a list. Rules that would have scored zero on every realistic corpus were
dropped; rules kept at zero here (`HTTPMethodCase`, `GenderNeutral`) are
regression guards on a corpus that is currently clean.

Only `error` blocks CI. `warning` and `suggestion` annotate without failing,
which is what keeps a linter installed past its first week.

## Testing the rules

```
make test
```

103 cases across all 22 rules: 49 that must alert, 53 that must stay silent,
and 1 documented false positive. The silent cases matter more — a rule with no
negative cases is indistinguishable from a rule that flags everything.

Before running fixtures, the suite preflights every rule file for
type-correctness. Vale drops a rule whose YAML does not type-check **without
reporting anything**; the rule simply stops firing.

The suite found four real defects during development:

| Defect | Consequence |
| --- | --- |
| `Acronyms` exempted `HTTP` but not `HTTPS`, and flagged `AND`/`OR` | noise on every page |
| `Terminology` matched `OAuth 2` inside the correct `OAuth 2.0` | RE2 has no lookahead, so the alternation needed anchoring |
| Unquoted `NULL`/`TRUE`/`FALSE` in an exception list | YAML 1.1 coerced them to null/bool and Vale silently dropped the entire rule |
| `API` in Vale's `Vocab` | **silently disabled `ApiKeyCase` and its 49 real violations** |

That last one is worth dwelling on. Vale's `accept.txt` is not a spelling
dictionary — it is a *global alert filter*, and any alert whose match overlaps
an accepted term is dropped across every rule. The vocabulary therefore lives
in `styles/vocabulary/accept.txt` and is compiled into **per-rule** exceptions
by `tools/sync_vocab.py`. `Vocab` is left unset on purpose.

## Vocabulary is the adoption cost

`HeadingSentenceCase` fired 167 times with an empty vocabulary, almost all of
them product names (`Install Meilisearch`, `When to choose Algolia`). With 185
accepted terms it fires 75 times. `Acronyms` went from 365 to 139 the same way.

Generic English words that appear inside product names — `Search`, `Cloud`,
`Index`, `Server` — are deliberately **not** accepted. Exempting them would
silence real title-case violations like `Configure Your Search Settings`.

What remains flagged is the rule working: `ION`, `BGE`, `HNSW` and `GIN` are
genuinely domain-specific and genuinely undefined on the pages that use them.

Curating this file is the real week-one work of adopting a docs linter. It is
not a rule-authoring problem.

## Remediation, and what is deliberately not automated

```
make report
```

10 of 22 rules are mechanically fixable. The other 12 are not, and the report
says so rather than implying the backlog is fully automatable:

| Not automated | Why |
| --- | --- |
| `Filler` | deleting "simply" can leave a sentence that no longer parses |
| `FirstPerson` | requires knowing whether "we" means the product, the team, or the reader |
| `Hedging` | requires deciding whether a step is required — a judgement about the API |
| `HeadingSentenceCase` | cannot tell a product name from a capitalised common noun |
| `LinkText` | the replacement is the destination's subject, which means reading it |
| `SentenceLength` | splitting a sentence requires understanding it |

### Code samples are never touched

```
make verify
```

> 16,541 protected segments across 553 files are byte-identical.

Remediation edits raw bytes and has no parser protecting it, so every fenced
block, indented code block, inline code span, link target and frontmatter block
is compared before and after. A style fix that breaks a code sample costs far
more than the violation it replaced.

Two masking bugs were caught this way and are worth naming:

- **Anchors at mask boundaries.** Masking inline code spans moved `$` to the
  mask boundary rather than end-of-line, so
  `##### Response: \`201 Created\`` lost its colon. Line-anchored rules now use
  a second view of the document that masks only whole-line constructs.
- **Indented code blocks in MDX.** A naive `^ {4}` match found 539 indented
  lines outside fences in this corpus, of which **zero** were code — every one
  was a `<Card>` body or a list continuation. Detection now applies
  CommonMark's actual precondition (preceded by a blank line, not a list or JSX
  continuation).

Quoted strings are also protected for deletion-type fixes: rewriting
`"High demand right now. Please wait a moment."` would make the docs describe
an error message the product never emits.

## CI

```yaml
- uses: ./docs-style-linter
  with:
    paths: docs
    fail-on: error
    changed-only: true
    sarif: true
    comment: true
```

The action installs Vale from a **checksum-pinned** release (a linter runs on
every pull request, so its binary is a supply-chain surface), runs it once, and
feeds that single JSON payload to four consumers: inline annotations, the job
summary, the pass/fail gate, and a SARIF upload.

`changed-only: true` is the important input. A team that opens a linter on
50,000 historical alerts turns it off the same afternoon. Gate the diff; pay
down the backlog separately with `make report`.

The SARIF includes a populated `rules[]` array built from the rule files
themselves, so clicking an annotation in code scanning shows the rule's
rationale and source link rather than a bare regex match.

`.github/workflows/ci.yml` also fails if `reports/before-after.md` is stale,
so the numbers in this README cannot drift from the code that produces them.

## Adding your own rules

`styles/TikTokDocs/` contains only rules traceable to a public source. To layer
an internal style guide on top:

1. Create `styles/Internal/` and add rule files there.
2. Set `BasedOnStyles = TikTokDocs, Internal` in `.vale.ini`.
3. Add fixtures to `tests/rules.yml` — `make test` fails on any rule without
   them, which is deliberate: an untested rule looks exactly like a passing one.

Keeping internal rules in a separate directory means the public package stays
publishable and the two sets can have different review requirements.

## Requirements

Vale 3.9.6 (`make install`), Python 3.9+, PyYAML.
