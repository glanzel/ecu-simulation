# Web-App (FastAPI + uvicorn), Abhängigkeiten wie in README: ``uv sync --group web``
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
ENV UV_HTTP_TIMEOUT=300
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock README.md oxyde_config.py ./
COPY logic simulation cms ui ./
RUN uv sync --frozen --group web --no-editable

FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:/usr/local/bin:$PATH" \
    VIRTUAL_ENV="/app/.venv" \
    UV_PROJECT_ENVIRONMENT="/app/.venv" \
    UV_NO_SYNC=1
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/oxyde_config.py /app/oxyde_config.py
COPY scripts/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh
ENV PORT=8000
EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
