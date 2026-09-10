.PHONY: dev test lint format-check format docker-build docker-build-prod clean setup

AI_ENGINE_PORT ?= 8003

dev:
	uv run uvicorn app.main:app --host 0.0.0.0 --port $(AI_ENGINE_PORT) --reload

test:
	uv run pytest

test-cov:
	uv run pytest --cov=app --cov-report=html --cov-report=term-missing

lint:
	uv run ruff check app/

typecheck:
	uv run mypy app/

format-check:
	uv run ruff format app/ --check

format:
	uv run ruff format app/

docker-build:
	docker compose --profile full build

docker-build-prod:
	docker build --target production -t product-graph-ai-engine .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov .mypy_cache .ruff_cache

setup:
	cp -n .env.example .env || true
	uv sync --extra dev
