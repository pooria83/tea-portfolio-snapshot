.PHONY: dev test test-cov lint lint-fix typecheck format-check format migrate migration seed clean setup ts-types docker-build docker-build-prod security precommit

API_PORT ?= 8000

dev:
	uv run uvicorn app.main:app --host 0.0.0.0 --port $(API_PORT) --reload

run:
	uv run fastapi run app/main.py --host 0.0.0.0 --port $(API_PORT) --proxy-headers

test:
	uv run pytest

test-cov:
	uv run pytest --cov=app --cov-report=html --cov-report=term-missing

lint:
	uv run ruff check app/ tests/ scripts/

lint-fix:
	uv run ruff check --fix app/ tests/ scripts/

typecheck:
	uv run mypy app/

format-check:
	uv run ruff format app/ tests/ scripts/ --check

format:
	uv run ruff format app/ tests/ scripts/

migrate:
	uv run alembic upgrade head

migration:
	uv run alembic revision --autogenerate -m "$(message)"

seed:
	uv run python scripts/seed.py
	uv run python scripts/seed_product_definitions.py
	uv run python scripts/seed_stores.py

setup:
	cp -n .env.example .env || true
	uv sync --dev
	uv run alembic upgrade head
	uv run python scripts/seed.py

ts-types:
	./scripts/generate_ts_types.sh

docker-build:
	docker compose --profile full build

docker-build-prod:
	docker build --target production -t product-graph-api .

security:
	uv run pip-audit

precommit:
	uv run pre-commit run --all-files

coverage-html:
	uv run pytest --cov=app --cov-report=html
	@echo "Open htmlcov/index.html in your browser"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov .mypy_cache .ruff_cache api-client-types test.db test_debug*.db
