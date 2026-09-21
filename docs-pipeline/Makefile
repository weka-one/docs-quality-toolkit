# Documentation monitor.

CONFIG ?= config.demo.yml
PY     ?= python3

.PHONY: help install browser test run render dashboard demo clean

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

install: ## Install dependencies
	$(PY) -m pip install -r requirements.txt

browser: ## Install the headless browser (only needed for render: true)
	$(PY) -m pip install -r requirements-browser.txt
	$(PY) -m playwright install chromium

test: ## Unit tests for the source adapters
	$(PY) -m pytest tests -q

run: ## One monitoring run against $(CONFIG)
	$(PY) pipeline/run.py --config $(CONFIG)

render: ## Render one page and show its text: make render URL=https://...
	@test -n "$(URL)" || { echo "Usage: make render URL=https://example.com/doc/x"; exit 2; }
	$(PY) pipeline/render.py "$(URL)"

dashboard: ## Rebuild the HTML report from run history
	$(PY) pipeline/dashboard.py --history history --out reports/dashboard.html

demo: ## Reproduce the committed demo: two runs over two real corpus states
	rm -f history/*.json
	$(PY) pipeline/run.py --config config.demo.yml --label "As published"
	$(PY) pipeline/run.py --config config.demo.yml \
	  --source-root ../docs-style-linter/build/after --label "After remediation"
	$(MAKE) dashboard

clean:
	rm -rf reports/*.json reports/*.html .pytest_cache **/__pycache__
