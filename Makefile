.DEFAULT_GOAL := help

UV ?= uv
PYTEST ?= $(UV) run pytest
RUFF ?= $(shell command -v ruff 2>/dev/null || echo "uvx ruff")

.PHONY: help install test test-fast lint format check build clean

help: ## Show this help message
	@printf "Usage: make [command]\n\n"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies with uv
	$(UV) sync

test: ## Run test suite with coverage
	$(PYTEST)

test-fast: ## Run tests quickly without coverage
	$(PYTEST) -o addopts=""

lint: ## Run ruff linter
	$(RUFF) check src tests

format: ## Format code with ruff
	$(RUFF) format src tests

check: ## Run lint, format check, and tests
	$(RUFF) check src tests
	$(RUFF) format --check src tests
	$(PYTEST)

build: ## Build distribution packages (wheel and sdist)
	$(UV) build

clean: ## Remove build artifacts, caches, and coverage data
	rm -rf dist build *.egg-info .pytest_cache .ruff_cache htmlcov .coverage .coverage.*
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.py[cod]" -delete 2>/dev/null || true
