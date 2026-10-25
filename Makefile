# Python version is pinned via `.python-version` (used by uv and CI).
PYTHON_VERSION := $(shell tr -d '[:space:]' < .python-version)

# Variables
UV = uv
UV_RUN = $(UV) run --locked
PYTEST_CMD = $(UV_RUN) python -m pytest -v
COVERAGE_OPTS = --cov --cov-report=term-missing --cov-report=html

# Include environment file
ifneq (,$(wildcard .env))
    include .env
    export
endif

################################################################################

.PHONY: all audit clean dead-code format help install lint runtime run smoke test

# Default target
help: ## Show this help message
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

################################################################################

# Development
install: ## Install all dependencies (including dev)
	@echo "Installing dependencies..."
	$(UV) python install $(PYTHON_VERSION)
	$(UV) sync --locked --python $(PYTHON_VERSION)
	@echo "Installing pre-commit hooks..."
	$(UV_RUN) pre-commit install

runtime: ## Install runtime dependencies only
	@echo "Installing runtime dependencies..."
	$(UV) python install $(PYTHON_VERSION)
	$(UV) sync --locked --python $(PYTHON_VERSION) --no-group dev

# Code quality
format: ## Format code
	@echo "Formatting code..."
	$(UV_RUN) black . && $(UV_RUN) isort .

lint: ## Run linting tools
	@echo "Running linting tools..."
	$(UV_RUN) black --check . && $(UV_RUN) isort --check-only . && $(UV_RUN) flake8 . && $(UV_RUN) mypy . && $(UV_RUN) bandit -r -c pyproject.toml .

dead-code: ## Check for dead code using vulture
	@echo "Checking for dead code..."
	$(UV_RUN) vulture .

# Testing
test: ## Run unit tests (excludes integration)
	@echo "Running unit tests with coverage..."
	$(PYTEST_CMD) $(COVERAGE_OPTS)

smoke: ## Run integration smoke tests (requires running services)
	@echo "Running integration smoke tests..."
	$(UV_RUN) python -m pytest tests/test_integration.py -v -o "addopts=" --no-header

# Combined operations
audit: ## Check dependencies for known vulnerabilities
	@echo "Auditing dependencies..."
	$(UV_RUN) pip-audit

all: lint test dead-code ## Run lint, test, and dead-code check
	@echo "All checks completed successfully!"

# Application
run: ## Run the setup script (requires LOCAL_API_KEY, CLOUD_API_KEY, CLOUD_BASE_URL)
	@echo "Running setup..."
	$(UV_RUN) python main.py

# Maintenance
clean: ## Clean cache and temporary files
	@echo "Cleaning cache and temporary files..."
	rm -rf .mypy_cache/ .pytest_cache/ .venv/ .coverage htmlcov/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
