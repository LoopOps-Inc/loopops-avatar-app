# actinver-agent developer targets. Run from services/agent.
SHELL := /bin/bash
.DEFAULT_GOAL := help

PY      ?= .venv/bin/python
UV      ?= uv
COMPOSE ?= docker compose
BASE    ?= http://localhost:8443
CLIENT  ?= cl_demo_moderado
ROLES   ?=

.PHONY: help install lint typecheck test test-integration up down logs migrate seed openapi token smoke build sbom clean

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Create .venv (Python 3.12) and install with dev extras
	$(UV) venv --python 3.12 .venv
	$(UV) pip install -e '.[dev]'

lint: ## Ruff (includes S bandit rules and ASYNC)
	$(PY) -m ruff check src tests scripts
	$(PY) -m ruff format --check src tests scripts

typecheck: ## mypy --strict
	$(PY) -m mypy src

test: ## Unit, graph, contract, adversarial and build-time assertions (80 % floor)
	$(PY) -m pytest -q

test-integration: ## End-to-end against the running compose stack
	AGENT_BASE_URL=$(BASE) $(PY) -m pytest -q -m integration --no-cov tests/integration

up: ## Build and start the full local stack
	$(COMPOSE) up -d --build

down: ## Stop the stack (keeps volumes; `make clean` removes them)
	$(COMPOSE) down

logs: ## Tail agent + controls
	$(COMPOSE) logs -f agent suitability guardrail audit transaction

migrate: ## Run Alembic migrations inside the stack
	$(COMPOSE) run --rm migrate

seed: ## Seed secrets (floci) and the retrieval corpus
	bash scripts/seed_local.sh

openapi: ## Export OpenAPI 3.1 documents for every role to docs/openapi/
	$(PY) scripts/export_openapi.py --out docs/openapi

token: ## Mint a dev access token: make token CLIENT=cl_demo_moderado ROLES=compliance,risk
	@$(PY) scripts/dev_token.py --client $(CLIENT) $(if $(ROLES),--roles $(ROLES),) --export

smoke: ## Step-by-step smoke test against $(BASE)
	AGENT_BASE_URL=$(BASE) bash scripts/smoke.sh

build: ## Build the container image
	docker build -t actinver-agent:local .

sbom: ## CycloneDX SBOM for the image (requires syft)
	@command -v syft >/dev/null || { echo "syft not installed: https://github.com/anchore/syft"; exit 1; }
	syft actinver-agent:local -o cyclonedx-json > sbom.cdx.json && echo "wrote sbom.cdx.json"

clean: ## Remove containers, volumes, caches
	$(COMPOSE) down -v --remove-orphans
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov sbom.cdx.json

postman: ## Generate the Postman environment (tokens + device key) for docs/postman
	$(PY) scripts/postman_env.py --client $(CLIENT)

postman-check: ## Run the Postman collection end to end with Newman (needs npx + the stack up)
	scripts/postman_check.sh
