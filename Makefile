# Python version is pinned via `.python-version` (used by uv and CI).
PYTHON_VERSION := $(shell tr -d '[:space:]' < .python-version)

# Variables
PYTEST_CMD = uv run python -m pytest -v
COVERAGE_OPTS = --cov --cov-report=term-missing --cov-report=html

# Include environment file
ifneq (,$(wildcard .env))
    include .env
    export
endif

################################################################################

.PHONY: all audit clean dead-code format help install lint runtime run test

# Default target
help: ## Show this help message
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

################################################################################

# Development
install: ## Install all dependencies (including dev)
	@echo "Installing dependencies..."
	uv python install $(PYTHON_VERSION)
	uv sync --python $(PYTHON_VERSION)
	@echo "Installing pre-commit hooks..."
	uv run pre-commit install

runtime: ## Install runtime dependencies only
	@echo "Installing runtime dependencies..."
	uv python install $(PYTHON_VERSION)
	uv sync --python $(PYTHON_VERSION) --no-group dev

# Code quality
format: ## Format code
	@echo "Formatting code..."
	uv run black . && uv run isort .

lint: ## Run linting tools
	@echo "Running linting tools..."
	uv run black --check . && uv run isort --check-only . && uv run flake8 . && uv run mypy . && uv run bandit -r -c pyproject.toml .

dead-code: ## Check for dead code using vulture
	@echo "Checking for dead code..."
	uv run vulture .

# Testing
test: ## Run unit tests (excludes integration)
	@echo "Running unit tests with coverage..."
	$(PYTEST_CMD) $(COVERAGE_OPTS)

smoke-test: ## Run integration smoke tests (requires running services)
	@echo "Running integration smoke tests..."
	uv run python -m pytest tests/test_integration.py -v -o "addopts=" --no-header

# Combined operations
audit: ## Check dependencies for known vulnerabilities
	@echo "Auditing dependencies..."
	uv run pip-audit

all: lint test dead-code ## Run lint, test, and dead-code check
	@echo "All checks completed successfully!"

# Application
run: ## Run the setup script (requires LOCAL_API_KEY, CLOUD_API_KEY, CLOUD_BASE_URL)
	@echo "Running setup..."
	uv run python main.py

# Maintenance
clean: ## Clean cache and temporary files
	@echo "Cleaning cache and temporary files..."
	rm -rf .mypy_cache/ .pytest_cache/ .venv/ .coverage htmlcov/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
