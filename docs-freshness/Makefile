# Docs freshness checker: test, check, evaluate.

DOCS ?= ../corpus/meilisearch-docs
SPEC ?= ../spec/meilisearch-openapi.json
PY   ?= python3

.PHONY: help install test check review eval eval-claude mutate thresholds clean

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-14s %s\n", $$1, $$2}'

install: ## Install dependencies
	$(PY) -m pip install -r requirements.txt

test: ## Unit tests
	$(PY) -m pytest tests -q

check: ## Run the checker over the corpus at the default gate
	$(PY) -m freshness --docs $(DOCS) --spec $(SPEC)

review: ## Show only the review queue (everything below the gate)
	$(PY) -m freshness --docs $(DOCS) --spec $(SPEC) --min-confidence 1.1

mutate: ## Regenerate the seeded-drift evaluation pages
	$(PY) eval/mutations.py --corpus $(DOCS) --spec $(SPEC) --count 20

eval: ## Score every offline arm and refresh the committed report
	$(PY) eval/harness.py --json eval/results/latest.json --out-md eval/results/latest.md

eval-claude: ## Score the LLM arm (needs ANTHROPIC_API_KEY); records a replay cache
	$(PY) eval/harness.py --adjudicator claude --cache eval/llm_cache.json \
	  --json eval/results/claude.json --out-md eval/results/claude.md

thresholds: ## CI gate: fail if any committed floor regresses
	$(PY) eval/harness.py --check-thresholds

clean:
	rm -rf eval/mutated .pytest_cache **/__pycache__
