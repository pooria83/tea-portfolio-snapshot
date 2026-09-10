FROM python:3.14-slim AS base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

FROM base AS dev
COPY . .
EXPOSE 8003
CMD ["uv", "run", "fastapi", "dev", "app/main.py", "--host", "0.0.0.0", "--port", "8003", "--reload"]

FROM python:3.14-slim AS production
ENV VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN adduser --disabled-password --uid 1000 appuser
RUN mkdir -p /data && chown appuser:appuser /data
COPY --from=base /app/.venv .venv
COPY app app
USER appuser
EXPOSE 8003
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:8003/health || exit 1
CMD ["fastapi", "run", "app/main.py", "--port", "8003", "--proxy-headers"]
