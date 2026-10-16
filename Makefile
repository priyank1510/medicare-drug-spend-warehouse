# Medicare Drug Spend Warehouse
# Docker targets need only Docker. local-* targets need Python 3.10+.

.DEFAULT_GOAL := help
SHELL := /bin/bash

HOST_UID ?= $(shell id -u)
HOST_GID ?= $(shell id -g)
export HOST_UID HOST_GID

COMPOSE := docker compose --profile cli
RUN     := $(COMPOSE) run --rm pipeline
DB      := data/warehouse/drugspend.duckdb

.PHONY: help up run test sql shell download-cms down clean local-setup local-run local-test

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Build the image and start the docs server (http://localhost:8080)
	mkdir -p dbt/target
	$(COMPOSE) build pipeline
	$(COMPOSE) up -d docs
	@echo "Docs server: http://localhost:8080 (populated after 'make run')"

run: ## Generate -> ingest -> dbt build (models + tests) -> defect report
	$(RUN) python -m drugspend.cli run
	@echo "Report: data/reports/defect_report.md   Docs: http://localhost:8080"

test: ## Run pytest (unit + end-to-end) inside the container
	$(RUN) python -m pytest -q

sql: ## Query the warehouse, e.g. make sql Q="select * from marts.mart_drug_spend_trend limit 5"
	$(RUN) python -c "import duckdb, sys; print(duckdb.connect('$(DB)', read_only=True).sql(sys.argv[1]))" "$(Q)"

shell: ## Open a shell in the pipeline container
	$(RUN) bash

download-cms: ## Pull a REAL CMS extract, e.g. make download-cms STATE=WI YEAR=2023
	$(RUN) python -m drugspend.cli download-cms --state $(or $(STATE),WI) --year $(or $(YEAR),2023)

down: ## Stop containers (keeps data and images for a fast restart)
	$(COMPOSE) down --remove-orphans

clean: ## Restore your machine: remove containers, images, volumes, venv and all generated files
	-$(COMPOSE) down --volumes --rmi all --remove-orphans
	rm -rf data/landing data/bronze data/warehouse data/reports \
	       dbt/target dbt/logs dbt/dbt_packages dbt/.user.yml .pytest_cache .venv
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	@echo "Done. Only the source code is left."
	@echo "Optional: 'docker builder prune' frees Docker's build cache (shared by all projects)."

local-setup: ## Create .venv and install dependencies (no Docker)
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

local-run: ## Run the pipeline from .venv
	PYTHONPATH=src .venv/bin/python -m drugspend.cli run

local-test: ## Run pytest from .venv
	PYTHONPATH=src PATH="$(CURDIR)/.venv/bin:$$PATH" .venv/bin/python -m pytest -q
