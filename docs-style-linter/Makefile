# Style linter: test, measure, and regenerate committed reports.
#
# CORPUS defaults to the vendored MIT corpus. Point it at your own docs to try
# the rule package against them:
#     make report CORPUS=../../my-docs

VALE_VERSION ?= 3.9.6
CORPUS       ?= ../corpus/meilisearch-docs
BUILD        ?= build/after
PY           ?= python3

.PHONY: help test lint vocab vocab-check report sarif verify clean install-vale

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-14s %s\n", $$1, $$2}'

install-vale: ## Install the pinned Vale release
	go install github.com/errata-ai/vale/v3/cmd/vale@v$(VALE_VERSION)

test: vocab-check ## Run the rule fixture suite
	$(PY) tools/ruletest.py

lint: ## Lint the corpus and print a single-run report
	$(PY) tools/report.py --target $(CORPUS)

vocab: ## Regenerate rule exceptions from styles/vocabulary/accept.txt
	$(PY) tools/sync_vocab.py

vocab-check: ## Fail if rule exceptions are stale
	$(PY) tools/sync_vocab.py --check

$(BUILD): ## Apply the deterministic remediation pass
	$(PY) tools/remediate.py --src $(CORPUS) --dst $(BUILD) --json reports/remediation.json

verify: $(BUILD) ## Prove remediation touched no code sample
	$(PY) tools/verify_codeblocks.py $(CORPUS) $(BUILD)

report: test $(BUILD) verify ## Regenerate the committed before/after report
	$(PY) tools/report.py --before $(CORPUS) --after $(BUILD) \
	  --out-json reports/before-after.json --out-md reports/before-after.md

sarif: ## Write a SARIF report for code scanning
	$(PY) tools/sarif.py --target $(CORPUS) --out reports/vale.sarif --repo-root ..

clean:
	rm -rf build
