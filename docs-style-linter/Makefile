# Style linter: test, measure, and regenerate committed reports.
#
# CORPUS defaults to the vendored MIT corpus. Point it at your own docs to try
# the rule package against them:
#     make report CORPUS=../../my-docs

VALE_VERSION ?= 3.9.6
CORPUS       ?= ../corpus/meilisearch-docs
BUILD        ?= build/after
# Structural policy. config/tiktok.yml is the house style; the corpus follows
# its own conventions, so measuring it uses its own policy file.
POLICY       ?= config/evaluation-corpus.yml
PY           ?= python3

.PHONY: help doctor install install-vale test lint structure vocab vocab-check report sarif verify clean

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-14s %s\n", $$1, $$2}'

doctor: ## Check that everything needed is installed, and say what is missing
	@$(PY) tools/doctor.py

install: ## Install everything needed (Python packages and Vale)
	$(PY) -m pip install -r requirements.txt
	./tools/install_vale.sh

install-vale: ## Install just the pinned Vale release (no Go or Homebrew needed)
	./tools/install_vale.sh

test: vocab-check ## Run the rule fixture suite
	$(PY) tools/ruletest.py

lint: ## Lint the corpus and print a single-run report
	$(PY) tools/report.py --target $(CORPUS)

structure: ## Run the structural checks Vale cannot express
	$(PY) tools/structure_lint.py $(CORPUS) --config $(POLICY) --out reports/structure.md

vocab: ## Regenerate rule exceptions from styles/vocabulary/accept.txt
	$(PY) tools/sync_vocab.py

vocab-check: ## Fail if rule exceptions are stale
	$(PY) tools/sync_vocab.py --check

$(BUILD): ## Apply the deterministic remediation pass
	$(PY) tools/remediate.py --src $(CORPUS) --dst $(BUILD) --json reports/remediation.json

verify: $(BUILD) ## Prove remediation touched no code sample
	$(PY) tools/verify_codeblocks.py $(CORPUS) $(BUILD)

report: test $(BUILD) verify structure ## Regenerate every committed report
	$(PY) tools/report.py --before $(CORPUS) --after $(BUILD) \
	  --out-json reports/before-after.json --out-md reports/before-after.md

sarif: ## Write a SARIF report for code scanning
	$(PY) tools/sarif.py --target $(CORPUS) --out reports/vale.sarif --repo-root ..

clean:
	rm -rf build
