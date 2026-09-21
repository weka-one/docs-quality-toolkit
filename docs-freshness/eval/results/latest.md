# Freshness checker evaluation

**26 hand-labelled corpus pages** and **20 mutated pages** (one injected defect each).

## Arms

| Arm | Base scoping | Corpus precision | Probe recall | Mutated recall | FP | FN |
| --- | :---: | ---: | ---: | ---: | ---: | ---: |
| `naive` | no | 0.35 | 1.00 | 1.00 | 39 | 0 |
| `none` | yes | 0.41 | 1.00 | 1.00 | 30 | 0 |
| `heuristic` | yes | 0.41 | 1.00 | 1.00 | 30 | 0 |

`naive` is an ablation with base-URL scoping disabled. It is not a shipping
configuration - it shows what the precision column costs without it.

## Recall by label source

| Source | TP | FN | Recall | Meaning |
| --- | ---: | ---: | ---: | --- |
| `adjudicated` | 19 | 0 | 1.00 | **Circular.** Labelled from this tool's own output; recall here is 1.0 by construction and is not a measurement. |
| `probe` | 2 | 0 | 1.00 | Built independently of the tool, by checking every inline `METHOD /path` and table-documented field against the spec by hand. **This is the real recall number.** |
| `mutated` | 20 | 0 | 1.00 | Constructed ground truth; exact recall against drift of the kinds modelled in `mutations.py`. |

## Per detector (arm: `none`)

| Detector | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| `missing_auth` | 15 | 0 | 0 | 1.00 | 1.00 |
| `unknown_endpoint` | 16 | 30 | 0 | 0.35 | 1.00 |
| `unknown_enum_value` | 4 | 0 | 0 | 1.00 | 1.00 |
| `unknown_parameter` | 6 | 0 | 0 | 1.00 | 1.00 |

## Gate threshold sweep (arm: `none`, corpus pages)

| Min confidence | Reported | TP | FP | Precision | Recall |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00 | 51 | 21 | 30 | 0.41 | 1.00 |
| 0.35 | 51 | 21 | 30 | 0.41 | 1.00 |
| 0.45 | 20 | 16 | 4 | 0.80 | 0.76 |
| 0.60 | 16 | 16 | 0 | 1.00 | 0.76 |
| 0.70 | 5 | 5 | 0 | 1.00 | 0.24 |
| 0.80 | 4 | 4 | 0 | 1.00 | 0.19 |
| 0.90 | 3 | 3 | 0 | 1.00 | 0.14 |

Findings below the gate are not discarded - they go to the review queue
(`--min-confidence` on the CLI controls the gate, `--review` prints the rest).

## False positives

- capabilities/full_text_search/overview.mdx: unknown_endpoint GET /search
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint DELETE /my-index
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint DELETE /my-index/_doc/{id}
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint GET /_cat/indices
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint GET /_cluster/health
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint GET /_tasks/{task_id}
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint GET /my-index
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint GET /my-index/_doc/{id}
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint GET /my-index/_settings
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint POST /_bulk
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint POST /_msearch
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint POST /_security/api_key
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint POST /my-index/_delete_by_query
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint POST /my-index/_doc
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint POST /my-index/_search
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint PUT /my-index
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint PUT /my-index/_settings
- resources/migration/qdrant_migration.mdx: unknown_endpoint DELETE /collections/{name}
- resources/migration/qdrant_migration.mdx: unknown_endpoint GET /collections
- resources/migration/qdrant_migration.mdx: unknown_endpoint GET /collections/{name}
- resources/migration/qdrant_migration.mdx: unknown_endpoint GET /collections/{name}/points/{id}
- resources/migration/qdrant_migration.mdx: unknown_endpoint GET /healthz
- resources/migration/qdrant_migration.mdx: unknown_endpoint POST /collections/{name}/points/delete
- resources/migration/qdrant_migration.mdx: unknown_endpoint POST /collections/{name}/points/scroll
- resources/migration/qdrant_migration.mdx: unknown_endpoint POST /collections/{name}/points/search
- resources/migration/qdrant_migration.mdx: unknown_endpoint POST /collections/{name}/points/search/batch
- resources/migration/qdrant_migration.mdx: unknown_endpoint POST /collections/{name}/snapshots
- resources/migration/qdrant_migration.mdx: unknown_endpoint PUT /collections/{name}
- resources/migration/qdrant_migration.mdx: unknown_endpoint PUT /collections/{name}/index
- resources/migration/qdrant_migration.mdx: unknown_endpoint PUT /collections/{name}/points

## What base-URL scoping prevents

The `naive` arm raises 39 false positive(s) that scoping removes. A sample of them:

- capabilities/analytics/advanced/migrate_analytics.mdx: unknown_endpoint POST /events
- capabilities/full_text_search/overview.mdx: unknown_endpoint GET /search
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint DELETE /my-index
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint DELETE /my-index/_doc/{id}
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint GET /_cat/indices
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint GET /_cluster/health
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint GET /_tasks/{task_id}
- resources/migration/elasticsearch_migration.mdx: unknown_endpoint GET /my-index

> 5 true positive(s) are marked ambiguous: the spec
> may be incomplete rather than the docs stale. Both need a human, so the
> rubric counts them as actionable. Subtract them to recompute without.
