# Documentation monitor

Runs the style linter, the structure linter and the freshness checker against
documentation that **does not live in Git**, and reports what changed since the
last run.

## Why this exists

The other two projects in this repository were built around a pull request: a
composite Action, inline annotations, `changed-only` diffing against a merge
base, SARIF upload to code scanning. That is the right design for docs-as-code
and the wrong one for a docs set whose system of record is a CMS. There is no
pull request to gate, no merge base to diff, and no file on disk until
something fetches it.

The checks themselves were never the problem — Vale, the structure linter and
the freshness checker all operate on text. What needed replacing was the layer
that produces the text and the layer that reports the results.

GitHub Actions is still the runner. It just runs on a cron against the CMS
instead of on a diff.

```
                 ┌─ FilesystemSource ─┐
   CMS ─────────►├─ CmsApiSource      ├──► staged tree ──► style ──┐
   published site├─ SiteCrawlSource  ─┘                   structure├──► snapshot
                 └────────────────────┘                   freshness┘        │
                                                                            ▼
                              history/*.json ◄── diff vs previous ──► dashboard.html
```

## Where content comes from

Three adapters, covering the three situations a docs team is actually in.

| Adapter | Use when |
| --- | --- |
| `FilesystemSource` | A directory, or an export the CMS produced |
| `CmsApiSource` | The CMS has a read API |
| `SiteCrawlSource` | It doesn't — read the published site from its sitemap |

No CMS is hardcoded, because the one this is aimed at is internal and its API
is not something this repository can know. `CmsApiSource` is described entirely
by configuration: a list endpoint, a pagination link, and the JSON paths to a
record's id, title, body and URL. Pointing it at a different CMS is a config
change.

`SiteCrawlSource` is the unglamorous fallback and the one most likely to be
needed. A CMS that cannot export and has no read API still serves HTML. It also
has a real advantage: it checks what readers actually see, rather than a source
of truth that may not match what was published.

Its HTML-to-Markdown reduction is deliberately small — headings, fenced code,
inline code, paragraph text, and nothing else. A fuller converter would invent
structure the checks would then treat as real.

## Reporting, and why it is not a gate

A gate blocks the one change in front of it. A monitor watches a corpus that
already has a backlog, and failing on the backlog trains everyone to ignore the
job. So:

- the run **fails on new error-level findings**, measured against the previous
  snapshot,
- the standing total is reported but never fails anything,
- findings are fingerprinted as `kind:check:page`, **without the line number**,
  so a reworded paragraph does not read as one finding fixed and one new.

Output is a self-contained HTML report, a JSON snapshot, and a job summary.

## The demo run

`make demo` reproduces the committed report. It is two real runs over two real
content states — the vendored corpus as published, and the same corpus after
the deterministic remediation pass — so the trend line is measured, not
invented:

| Run | Errors | Warnings | Suggestions | Total |
| --- | ---: | ---: | ---: | ---: |
| As published | 483 | 729 | 468 | 1,680 |
| After remediation | 383 | 486 | 423 | 1,292 |

233 findings fixed, 0 new. With one run the dashboard says so and draws no
trend rather than drawing a line through a single point.

### Chart decisions

- **Severity is a status encoding, not a categorical one**, so it uses the
  reserved status palette rather than series hues, and every severity appears
  with a glyph and a written label — in the tiles, at each line end, and in the
  table. Colour never carries meaning alone.
- The by-check chart is a **single series**, so it takes one validated hue and
  no legend; the title names it.
- Axis bounds round to whole steps. Scaling to the data's maximum produced an
  axis of 0/188/375/562/750.
- Both charts have a hover layer, and a table view carries everything the
  charts show.

Rendered and checked at 1060px and 390px in both themes.

## Commands

```
make install     dependencies
make test        11 unit tests for the source adapters
make run         one monitoring run
make dashboard   rebuild the report from history
make demo        reproduce the committed two-run demo
```

## Configuration

`config.example.yml` is commented for the CMS case; `config.demo.yml` points at
the vendored corpus. Credentials are read from the environment
(`auth_env: DOCS_CMS_TOKEN`) and never committed — the adapter refuses to run
if the variable is unset rather than silently fetching nothing.

## Safety

A CMS slug is untrusted input and the pipeline writes it to disk. `materialise`
refuses any path that resolves outside the staging directory, and there is a
test for it. The crawler will not leave the host named in its sitemap URL,
honours a delay between requests, and treats one failed page as a finding
rather than the end of the run.

## Requirements

Python 3.9+, PyYAML, and Vale 3.9.6 on `PATH` for the style checks.
