# Indexao Makefile
# Development and build commands

.PHONY: help dev test lint format demo build clean setup

help: ## Show this help message
	@echo "Indexao Makefile Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

setup: ## Setup development environment (venv + dependencies)
	@echo "🔧 Setting up development environment..."
	python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install pytest pytest-cov black ruff mypy
	@echo "✅ Done! Activate with: source venv/bin/activate"

dev: ## Install package in development mode (Python-only)
	pip install -e .

dev-rust: ## Install with Rust optimization (requires maturin)
	pip install maturin
	maturin develop

dev-release: ## Install with Rust optimization (release mode, fast)
	pip install maturin
	maturin develop --release

install-deps: ## Install all dependencies
	pip install -r requirements.txt

test: ## Run all tests
	pytest tests/ -v

test-unit: ## Run unit tests only
	pytest tests/unit/ -v

test-e2e: ## Run end-to-end tests only
	pytest tests/e2e/ -v

test-cov: ## Run tests with coverage report
	pytest tests/ --cov=indexao --cov-report=html --cov-report=term

lint: ## Run code linter (ruff)
	ruff check src/

lint-fix: ## Auto-fix linting issues
	ruff check --fix src/

format: ## Format code (black)
	black src/ tests/

type-check: ## Run type checker (mypy)
	mypy src/indexao/

demo: ## Run demo with sample data
	@echo "Indexing demo folder..."
	python -m indexao.cli index ../_Volumes/demo --translate fr,en,zh-TW
	@echo ""
	@echo "Searching for 'ballon'..."
	python -m indexao.cli search "ballon"
	@echo ""
	@echo "Viewing sport.txt in French..."
	python -m indexao.cli view ../_Volumes/demo/sport.txt --lang fr

build: ## Build wheel package
	python -m build

build-rust: ## Build Rust-optimized wheel (requires maturin)
	maturin build --release

clean: ## Clean build artifacts and cache
	rm -rf build/ dist/ *.egg-info
	rm -rf target/ Cargo.lock
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

clean-index: ## Clean index database (WARNING: deletes indexed data)
	@echo "WARNING: This will delete all indexed data!"
	@read -p "Are you sure? (y/N) " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf ../index/*; \
		echo "Index cleaned."; \
	fi

setup-meilisearch: ## Setup Meilisearch (downloads and runs)
	@echo "Downloading Meilisearch..."
	curl -L https://install.meilisearch.com | sh
	@echo ""
	@echo "Starting Meilisearch on http://localhost:7700"
	./meilisearch --no-analytics

ci-lint: ## CI: Run linting (no fixes)
	ruff check src/ --no-fix

ci-test: ## CI: Run tests with coverage
	pytest tests/ --cov=indexao --cov-report=xml --cov-report=term -v

ci-build: ## CI: Build wheel for distribution
	python -m build

docs: ## Build documentation (if using Sphinx)
	cd docs && make html

count-lines: ## Count lines of code
	@echo "Source code line count:"
	@find src/indexao -name "*.py" -exec wc -l {} + | tail -1
	@echo ""
	@echo "Files exceeding 400 lines (should be empty):"
	@find src/indexao -name "*.py" -exec sh -c 'lines=$$(wc -l < "$$1"); if [ $$lines -gt 400 ]; then echo "$$1: $$lines lines"; fi' _ {} \;

version: ## Show current version
	@python -c "from importlib.metadata import version; print(f'Indexao v{version(\"indexao\")}')"

.DEFAULT_GOAL := help
