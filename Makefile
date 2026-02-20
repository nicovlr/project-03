.PHONY: help install run api dashboard pipeline test lint format docker up down clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Local development
# ---------------------------------------------------------------------------

install: ## Install Python dependencies
	pip install -r requirements.txt
	pip install ruff pre-commit

run: api ## Alias for api

api: ## Start FastAPI dev server
	uvicorn app.main:app --reload --port 8000

dashboard: ## Start Streamlit dashboard
	streamlit run dashboard/app.py --server.port 8501

pipeline: ## Run the full ETL pipeline
	python -m app.pipeline

test: ## Run tests with pytest
	pytest tests/ -v --tb=short

lint: ## Lint with ruff
	ruff check .

format: ## Format with ruff
	ruff format .
	ruff check --fix .

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

docker: ## Build all Docker images
	docker compose build

up: ## Start all services (DB + API + Dashboard)
	docker compose up -d

down: ## Stop all services
	docker compose down

ingest: ## Run the ingestion pipeline via Docker
	docker compose --profile ingest run --rm pipeline

logs: ## Tail logs for all services
	docker compose logs -f

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

db-migrate: ## Run Alembic migrations
	alembic upgrade head

db-revision: ## Create a new Alembic revision (usage: make db-revision msg="add foo")
	alembic revision --autogenerate -m "$(msg)"

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache htmlcov .coverage dist build *.egg-info
