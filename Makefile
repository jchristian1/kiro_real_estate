.PHONY: help up down migrate test test-postgres lint typecheck build generate-secrets seed-dev

help: ## Show available targets
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

up: ## Start all services (builds images, runs in background)
	docker compose up --build -d

down: ## Stop all services
	docker compose down

migrate: ## Run database migrations (uses DATABASE_URL env var; falls back to SQLite)
	alembic upgrade head

migrate-postgres: ## Run migrations against Postgres (DATABASE_URL must be set to a postgresql:// URL)
	@if [ -z "$(DATABASE_URL)" ]; then \
		echo "ERROR: DATABASE_URL is not set."; \
		echo "  export DATABASE_URL=postgresql://user:pass@localhost:5432/dbname"; \
		exit 1; \
	fi
	@echo "Running migrations against: $(DATABASE_URL)"
	alembic upgrade head

test: ## Run all tests (SQLite-backed, fast — skips Postgres suite)
	pytest tests/ -x --ignore=tests/postgres

test-postgres: ## Run Postgres-backed tests (requires POSTGRES_TEST_URL env var)
	@if [ -z "$$POSTGRES_TEST_URL" ]; then \
		echo "ERROR: POSTGRES_TEST_URL is not set."; \
		echo "  export POSTGRES_TEST_URL=postgresql://user:pass@localhost:5432/test_db"; \
		exit 1; \
	fi
	pytest tests/postgres/ -v -m postgres

lint: ## Lint Python and TypeScript sources
	ruff check . && cd frontend && npx eslint src/

typecheck: ## Type-check Python and TypeScript sources
	mypy api/ gmail_lead_sync/ && cd frontend && npx tsc --noEmit

build: ## Build the frontend production bundle
	cd frontend && npm run build

generate-secrets: ## Generate cryptographically secure ENCRYPTION_KEY and SECRET_KEY
	bash scripts/generate_secrets.sh

seed-dev: ## Seed demo data for local development (requires ENVIRONMENT=development and DEV_ADMIN_PASSWORD)
	@if [ -z "$(DEV_ADMIN_PASSWORD)" ]; then \
		echo "ERROR: DEV_ADMIN_PASSWORD is not set."; \
		echo "  export DEV_ADMIN_PASSWORD='your-secure-password'"; \
		exit 1; \
	fi
	ENVIRONMENT=development DEV_SEED=true python scripts/seed_data.py
