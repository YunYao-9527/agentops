.PHONY: install dev lint format test run docker-up docker-down

install:
	pip install -e ".[dev]"

dev:
	pre-commit install
	cp -n .env.example .env 2>/dev/null || true

lint:
	ruff check src/ agentops/ tests/
	mypy src/ agentops/

format:
	ruff format src/ agentops/ tests/

test:
	pytest tests/ -v --cov=src --cov=agentops --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8080

run-prod:
	uvicorn src.main:app --host 0.0.0.0 --port 8080 --workers 4

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose build

db-migrate:
	alembic upgrade head

db-migrate-new:
	alembic revision --autogenerate -m "$(msg)"

init: install dev db-migrate
	@echo "Project initialized. Run 'make run' to start."
