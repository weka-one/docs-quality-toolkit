# Labelling rubric

Written **before** the labels, and applied mechanically, because the same
person built the detectors and labelled their output. That is a real bias risk
and the honest mitigation is a rule you can check the labels against rather
than a claim of impartiality.

## The question a label answers

> Would a documentation engineer have to change something because of this
> finding?

Not "is the finding factually true". `GET /meilisearch/meilisearch/latest/config.toml
does not appear in the spec` is perfectly true and entirely useless, because
that URL was never this API's to begin with. A checker is useful to the degree
its output is actionable, so that is what gets measured.

Either outcome counts as actionable:

- the documentation is wrong and needs fixing, or
- the specification is wrong or incomplete and needs fixing.

## True positive

- **`unknown_endpoint`** — the sample targets the API under test, and the
  method/path pair is absent from the spec. Includes a path that exists under
  other verbs only: a reader copying it gets 405.
- **`unknown_parameter`** — the field is sent to an operation whose schema does
  not accept it, and the operation genuinely declares a schema.
- **`unknown_enum_value`** — the value is documented as accepted for a field
  the spec constrains, and it is not in that constraint.
- **`missing_auth`** — a complete, copy-pasteable invocation of a secured
  operation with no credentials, on a page that does not tell the reader
  credentials are being omitted.

## False positive

- The sample targets a different service (a hosted analytics endpoint, a
  release tarball, a third-party API).
- The extracted "value" is not a value: a type name, a field referring to
  itself, a dotted settings path, a link target.
- The operation declares no schema, so the spec cannot contradict anything.
- The page states that credentials are omitted for brevity.
- The snippet is a fragment rather than a runnable command.

## Ambiguity

"The docs describe a route the spec does not contain" has two causes: the docs
are stale, or the spec is incomplete. Both are actionable, so both are labelled
true positive, and the record carries `ambiguous: true`. `PATCH
/chats/{workspace_uid}/indexes/{index_uid}` is the clearest example — an
experimental route that may simply be missing from a generated spec.

These records are reported separately in the harness output so a reader can
recompute the scores without them.

## Sources

| Source | Pages | What it measures |
| --- | --- | --- |
| `corpus` | hand-adjudicated real pages | precision in the wild, on drift nobody planted |
| `mutated` | seeded drift from `mutations.py` | recall against drift of known kinds |

Neither is sufficient alone. Real pages cannot measure recall without reading
every page against the spec by hand. Mutations cannot measure precision,
because a mutated page is known-bad by construction and says nothing about how
often the tool cries wolf on correct documentation.
