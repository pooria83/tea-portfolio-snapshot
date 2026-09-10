FROM python:3.14-slim AS base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

FROM base AS dev
COPY . .
EXPOSE 8000
CMD ["uv", "run", "fastapi", "dev", "app/main.py", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM python:3.14-slim AS production
ARG ENVIRONMENT=production
ARG GIT_SHA=unknown
ENV ENVIRONMENT=$ENVIRONMENT \
    GIT_SHA=$GIT_SHA \
    VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*
RUN adduser --disabled-password --uid 1000 appuser
WORKDIR /app
COPY --from=base /app/.venv .venv
COPY app app
COPY alembic alembic
COPY alembic.ini .
COPY scripts/seed*.py scripts/
COPY scripts/download_brand_logos.py scripts/
COPY scripts/seed_data scripts/seed_data
RUN mkdir -p /app/static
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:8000/api/v1/health || exit 1
CMD ["fastapi", "run", "app/main.py", "--port", "8000", "--proxy-headers"]
