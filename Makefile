.PHONY: help up down migrate test lint typecheck build generate-secrets

help: ## Show available targets
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

up: ## Start all services (builds images, runs in background)
	docker compose up --build -d

down: ## Stop all services
	docker compose down

migrate: ## Run database migrations
	alembic upgrade head

test: ## Run all tests (stops on first failure)
	pytest tests/ -x

lint: ## Lint Python and TypeScript sources
	ruff check . && cd frontend && npx eslint src/

typecheck: ## Type-check Python and TypeScript sources
	mypy api/ gmail_lead_sync/ && cd frontend && npx tsc --noEmit

build: ## Build the frontend production bundle
	cd frontend && npm run build

generate-secrets: ## Generate cryptographically secure ENCRYPTION_KEY and SECRET_KEY
	bash scripts/generate_secrets.sh
