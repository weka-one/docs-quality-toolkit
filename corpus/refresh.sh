#!/usr/bin/env bash
# Re-pin the vendored corpus and OpenAPI spec.
#
# Usage: ./refresh.sh [docs-ref] [meilisearch-version]
set -euo pipefail

DOCS_REF="${1:-main}"
MS_VERSION="${2:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "==> Cloning meilisearch/documentation @ ${DOCS_REF}"
git clone --depth 1 --branch "$DOCS_REF" --quiet \
  https://github.com/meilisearch/documentation "$WORK/docs" 2>/dev/null ||
  git clone --depth 1 --quiet https://github.com/meilisearch/documentation "$WORK/docs"

COMMIT="$(git -C "$WORK/docs" rev-parse HEAD)"
echo "    pinned at ${COMMIT}"

echo "==> Replacing corpus"
rm -rf "$HERE/meilisearch-docs"
mkdir -p "$HERE/meilisearch-docs"
for d in capabilities getting_started reference resources snippets; do
  [ -d "$WORK/docs/$d" ] || continue
  (cd "$WORK/docs" && find "$d" -name '*.mdx' -print0) |
    while IFS= read -r -d '' f; do
      mkdir -p "$HERE/meilisearch-docs/$(dirname "$f")"
      cp "$WORK/docs/$f" "$HERE/meilisearch-docs/$f"
    done
done
cp "$WORK/docs/LICENSE" "$HERE/meilisearch-docs/LICENSE"

if [ -z "$MS_VERSION" ]; then
  MS_VERSION="$(git ls-remote --tags --refs https://github.com/meilisearch/meilisearch |
    awk -F/ '{print $NF}' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)"
fi
echo "==> Downloading OpenAPI spec ${MS_VERSION}"
mkdir -p "$ROOT/spec"
curl -sSLf --max-time 120 \
  "https://github.com/meilisearch/meilisearch/releases/download/${MS_VERSION}/meilisearch-openapi.json" \
  -o "$ROOT/spec/meilisearch-openapi.json"

python3 -c "import json,sys; s=json.load(open('$ROOT/spec/meilisearch-openapi.json')); \
  print('    OpenAPI', s['openapi'], s['info']['version'], len(s['paths']), 'paths')"

cat <<MSG

Corpus: $(find "$HERE/meilisearch-docs" -name '*.mdx' | wc -l | tr -d ' ') pages @ ${COMMIT}
Spec:   ${MS_VERSION}

Committed metrics are now stale. Regenerate them:
  (cd "$ROOT/docs-style-linter" && make report)
  (cd "$ROOT/docs-freshness"    && make eval)
MSG
