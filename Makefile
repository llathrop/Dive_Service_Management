# =============================================================================
# Dive Service Management - Makefile
# Common development and deployment shortcuts
# =============================================================================
# Usage: make <target>
# Run 'make help' for a list of available targets.
# =============================================================================

.DEFAULT_GOAL := help
COMPOSE := docker compose
EXEC_WEB := $(COMPOSE) exec web
msg ?= auto

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

.PHONY: build
build: ## Build Docker images
	$(COMPOSE) build

.PHONY: up
up: ## Start all services in detached mode
	$(COMPOSE) up -d

.PHONY: down
down: ## Stop and remove containers
	$(COMPOSE) down

.PHONY: logs
logs: ## Tail logs from all containers
	$(COMPOSE) logs -f

.PHONY: shell
shell: ## Open a bash shell in the web container
	$(EXEC_WEB) bash

.PHONY: flask-shell
flask-shell: ## Open a Flask interactive shell
	$(EXEC_WEB) flask shell

.PHONY: restart
restart: ## Restart all services
	$(COMPOSE) restart

.PHONY: ps
ps: ## Show status of all containers
	$(COMPOSE) ps

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

.PHONY: migrate
migrate: ## Create a new migration (use: make migrate msg="description")
	$(EXEC_WEB) flask db migrate -m "$(msg)"

.PHONY: upgrade
upgrade: ## Run database migrations (upgrade to head)
	$(EXEC_WEB) flask db upgrade

.PHONY: downgrade
downgrade: ## Rollback last database migration
	$(EXEC_WEB) flask db downgrade

.PHONY: seed
seed: ## Seed the database with default data
	$(EXEC_WEB) flask seed-db

.PHONY: create-admin
create-admin: ## Create an admin user interactively
	$(EXEC_WEB) flask create-admin

# ---------------------------------------------------------------------------
# Testing (Docker-based)
# ---------------------------------------------------------------------------

COMPOSE_TEST := docker compose -f docker-compose.test.yml

.PHONY: test-build
test-build: ## Build the test container
	$(COMPOSE_TEST) build

.PHONY: test
test: ## Run full test suite in Docker container
	$(COMPOSE_TEST) run --rm test

.PHONY: test-smoke
test-smoke: ## Run smoke tests only in Docker
	$(COMPOSE_TEST) run --rm test python -m pytest tests/smoke/ -x -v

.PHONY: test-unit
test-unit: ## Run unit tests only in Docker, stop on first failure
	$(COMPOSE_TEST) run --rm test python -m pytest tests/unit/ -x --tb=short -v

.PHONY: test-blueprint
test-blueprint: ## Run blueprint (route) tests only in Docker
	$(COMPOSE_TEST) run --rm test python -m pytest tests/blueprint/ -x --tb=short -v

.PHONY: test-validation
test-validation: ## Run end-to-end validation tests in Docker (verbose)
	$(COMPOSE_TEST) run --rm test python -m pytest tests/validation/ -v --tb=long

.PHONY: test-fast
test-fast: ## Run smoke + unit tests in Docker (quick feedback loop)
	$(COMPOSE_TEST) run --rm test python -m pytest tests/smoke/ tests/unit/ -x --tb=short -v

.PHONY: test-cov
test-cov: ## Run tests with coverage report in Docker
	$(COMPOSE_TEST) run --rm test python -m pytest --cov=app --cov-report=term-missing -v

.PHONY: test-failed
test-failed: ## Re-run only last-failed tests in Docker
	$(COMPOSE_TEST) run --rm test python -m pytest --lf --tb=long -v

.PHONY: export-test
export-test: ## Run tests with coverage (export-ready)
	$(COMPOSE_TEST) run --rm test pytest --cov=app --cov-report=term-missing

# ---------------------------------------------------------------------------
# Linting
# ---------------------------------------------------------------------------

.PHONY: lint
lint: ## Run flake8 linter in the web container (install flake8 first if needed)
	$(EXEC_WEB) python -m flake8 app/ --max-line-length=120 --exclude=__pycache__,migrations || \
		echo "Note: flake8 not installed. Add it to requirements-dev.txt to enable linting."

# ---------------------------------------------------------------------------
# Backup / Restore
# ---------------------------------------------------------------------------

.PHONY: backup
backup: ## Backup the database to backups/ directory
	./scripts/backup.sh

.PHONY: restore
restore: ## Restore database from backup (use: make restore file=backups/dsm_YYYY...sql.gz)
	./scripts/restore.sh $(file)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

.PHONY: setup
setup: ## Run first-time setup script
	./scripts/setup.sh

.PHONY: setup-lightweight
setup-lightweight: ## Run setup with lightweight (Pi) profile
	DSM_DEPLOYMENT_PROFILE=lightweight ./scripts/setup.sh

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

.PHONY: clean
clean: ## Remove containers, volumes, and built images
	$(COMPOSE) down -v --rmi local

.PHONY: clean-pyc
clean-pyc: ## Remove Python bytecode files
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

.PHONY: help
help: ## Show this help message
	@echo "Dive Service Management - Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
