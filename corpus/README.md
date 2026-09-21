# Vendored evaluation corpus

Both projects in this repository need a **real** documentation corpus to produce
honest numbers. Synthetic docs written by the author of a linter will always
score well against that linter, which makes the resulting metrics worthless.

## What is here

| Path | Contents | Provenance |
| --- | --- | --- |
| `meilisearch-docs/` | 553 `.mdx` pages, 252,652 words (155,629 excluding code and frontmatter) | [`meilisearch/documentation`](https://github.com/meilisearch/documentation) @ `7b72487` (2026-09-16) |
| `../spec/meilisearch-openapi.json` | OpenAPI 3.1, 72 paths | Official release asset, [`meilisearch/meilisearch` v1.54.0](https://github.com/meilisearch/meilisearch/releases/tag/v1.54.0) |

## Why this corpus

It is shaped like the docs these tools are meant for — a developer platform
with OAuth-style credentials, REST endpoints, per-endpoint parameter tables,
error-code references, and multi-language code samples:

- `reference/api/` — authorization, headers, pagination, request conventions
- `reference/errors/` — error-code tables
- `capabilities/` — 163 conceptual and how-to pages
- `getting_started/` — quickstarts and SDK setup
- `snippets/generated-code-samples/` — 257 code samples in 11 languages

Critically, the project publishes a **machine-readable OpenAPI spec as a release
asset**, so the freshness checker in `../docs-freshness/` diffs documentation
against a genuine source of truth rather than one reconstructed from the docs it
is supposed to be checking.

## Licensing

The corpus is MIT licensed (see `meilisearch-docs/LICENSE`), which permits
redistribution. The OpenAPI spec is published by the same project under the same
terms. Nothing here is proprietary to any employer.

The `changelog/` directory was excluded: it is a single 149 KB file that would
dominate per-page metrics.

## Refreshing

`./refresh.sh` re-pins both the corpus and the spec. Re-pinning invalidates the
committed metrics in both projects' READMEs — regenerate them, do not edit them
by hand.
