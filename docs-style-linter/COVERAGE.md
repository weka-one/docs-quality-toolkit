# Style guide coverage

What the TT4D Documentation Style Guide 2.0 asks for, and what this repository
actually enforces. The point of the table is the third column: a linter that
does not say what it *cannot* check lets a team believe the checklist is done.

Appendix B of the guide is a 40-item pre-publish checklist. 23 of those items
are now machine-checked. The other 17 need a human, and saying which is which
is the useful part.

## How the checks are split

| Layer | Checks | Why there |
| --- | --- | --- |
| **Vale rules** (`styles/TikTokDocs/`) | 40 | Anything that is a judgement about a span of prose |
| **Structure linter** (`tools/structure_lint.py`) | 12 | Anything that needs document structure: heading trees, table columns, fence blocks, cross-page uniqueness |
| **Freshness checker** (`../docs-freshness/`) | 5 detectors | Anything that needs the API spec, not the prose |
| **Human** | — | Everything that requires knowing what the writer meant |

The split is not cosmetic. `RequirementColumn` — "the Required column accepts
only Yes, No, or Conditional" — was first written as a Vale rule scoped to
table cells. It flagged **90** cells on the evaluation corpus, because Vale has
no concept of which *column* a cell is in and every `true` in every table
matched. Moved to the structure linter, which reads the header row first, it
reports 10, all real.

## Guide sections → checks

| Guide section | Enforced by | Not enforced, and why |
| --- | --- | --- |
| Overview → Requirement keywords | `RequirementKeywords` | Choosing between must/should/can is a statement about the API |
| Overview → Timeless documentation | `TimelessDocs` | — |
| Overview → Voice and tone | `Editorializing`, `Filler`, `FirstPerson` | "Objective and instructive" as a whole |
| Abbreviations and acronyms | `Acronyms`, `AcronymPlural`, `LatinAbbreviations`, `FileTypes` | Whether an acronym is worth introducing at all |
| API reference → Required section order | `structure_lint` (heading hierarchy, H4 ban) | Full section-order validation needs a page-type signal the CMS does not expose yet |
| API reference → Naming endpoints | `HeadingCaseH1`, `structure_lint` (title uniqueness) | Whether the title is a verb phrase describing the operation |
| API reference → Endpoint summary table | `LegacyHost` | Full-URL and row-order checks need the table's semantic role |
| API reference → Parameter tables | `structure_lint` (column names, Required values), `DataTypes` | Whether a description states units, ranges, and defaults |
| API reference → Error codes | — | Sorting and Description/Resolution separation are structural but need the page type |
| API reference → Rate limits | — | Presence is structural; the sentence pattern is editorial |
| Bolding | — | Bolding rules depend on whether the bolded span is a UI label, a run-in heading, or emphasis |
| Callouts | `structure_lint` (labels, retired labels, format, stacking, density) | Whether the information deserved an interruption |
| Capitalization | `HeadingCaseH1`, `HeadingCaseH2Plus`, `ProductTerms` | — |
| Code → Code in text | `EndpointInCode`, `HTTPMethodCase`, `StatusCodeName` | The full Code-in-text table needs entity recognition |
| Code → Code samples | `structure_lint` (fence labels, lowercase, approved set) | "Verify that every sample runs" — the freshness checker covers the API contract, not execution |
| Emojis | — | Deliberately unenforced: the platform *requires* an emoji in callouts |
| Error messages and troubleshooting | — | Symptom → cause → resolution is a shape a human judges |
| Grammatical person | `FirstPerson` | Second vs third person depends on who acts |
| Headings | `HeadingPunctuation`, `structure_lint` (skips, duplicates, empty, single H1) | Parallelism among sibling H3s |
| Images → Referring to images | `DirectionalLanguage` | Alt-text quality |
| Instructional sets | — | Step granularity and ordering |
| Links and cross-references | `LinkText` | Whether anchor text describes the destination |
| Lists | — | Parallel construction needs parsing each item's grammar |
| Numbers and measurements | `Measurements` | The spell-out-below-10 rule inverts for technical quantities; deciding which is which needs context |
| Page structure | `structure_lint` (partially) | Template conformance needs a page-type signal |
| Placeholders and sample values | `Placeholders`, `structure_lint` (unexplained placeholders) | Whether a sample value is realistic |
| Punctuation | `EmDash`, `Exclamation`, `Semicolon`, `ForwardSlash`, `AndOr`, `HeadingPunctuation` | Comma and hyphen rules need part-of-speech tagging |
| Referencing the audience → Inclusive language | `InclusiveLanguage`, `GenderNeutral` | Idioms and cultural references |
| Release status and deprecation | — | A deprecation notice needs four facts; only a human knows the sunset date |
| Screen components | `ScreenComponents`, `UIActions`, `ActionVerbs` | Prepositions depend on which control is meant |
| Symbols | `Measurements` (percent spacing) | Ampersand usage depends on whether it is in the UI |
| Tables | `structure_lint` (column count, empty cells, column names) | "Introduce every table with a complete sentence" |
| Word list | `ProductTerms`, `ActionVerbs`, `VagueWords`, `Wordiness`, `AllowsYouTo`, `Please`, `NoteThat` | — |

## Appendix B, item by item

**Machine-checked (23)**

Heading levels sequential · every heading has text under it · every heading
unique · one H1 per page · page has a title · title unique across the doc set ·
Required column values · parameter column vocabulary · table column count ·
no empty table cells · every fence has a language · fence labels lowercase ·
fence labels approved · callout labels approved · no retired callout labels ·
callout format · no stacked callouts · callout density per section · no em
dashes · no exclamation points · no directional language · no words from the
avoid list · placeholders use UPPERCASE_WITH_UNDERSCORES

**Human-only (17)**

Page uses one of the four templates · title matches the nav label · reference
sections in the required order · endpoint summary table shape · nested objects
have their own H3 · descriptions state units and defaults · Boolean description
patterns · rate limit stated · error codes sorted with resolutions · second
person, present tense, active voice · must/should/can used precisely · lists
parallel and consistently punctuated · code font applied per the Code-in-text
table · every code sample has been run · no real tokens or user data ·
screenshots have alt text and no sensitive data · every link resolves

Two of those are closer than they look. "Every code sample has been run" is
partly covered by `../docs-freshness/`, which checks samples against the
OpenAPI spec — it cannot execute them, but it catches a sample calling an
endpoint or parameter that does not exist. "Every link resolves" is a link
checker away and is the obvious next thing to add.

## What the evaluation corpus can and cannot validate

The rules are measured against a borrowed corpus (Meilisearch docs, MIT). That
validates the **mechanism** — that a rule fires where it should and stays quiet
where it should not — and it validates the generic conventions, because those
are shared across technical writing.

It cannot validate the TT4D-specific rules. `ProductTerms` scores 2 on this
corpus and `LegacyHost` scores 0, because the corpus has never heard of
`open-api.tiktok.com`. Those rules are validated only by the fixture suite in
`tests/rules.yml`, and that limitation is real: their first contact with actual
TT4D content will surface false positives this repository has no way to predict.

The structure linter has the same split, handled explicitly. Its policy lives
in `config/*.yml`, not in the code: `config/tiktok.yml` holds TT4D's decisions,
`config/evaluation-corpus.yml` holds the corpus's. Measuring the corpus against
TT4D's policy produced 552 "missing H1" issues (this corpus puts titles in
frontmatter) and 1,193 "unapproved fence" issues (it documents Go, Rust, PHP,
Ruby, C#, Dart and Swift). Neither is a defect. Reporting them as such would
have made the numbers meaningless.

## Provenance

No proprietary content from the style guide is reproduced here. Each rule file
cites the guide section it implements plus a public corroborating source
(Google developer documentation style guide, Microsoft Writing Style Guide, RFC
9110, WCAG 2.2, AP style) where one exists. Product and platform terms are
those published on the public developer site. Internal links, internal
glossaries, the known-issues list, and the guide's prose are not in this
repository.
