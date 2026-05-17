# Web-App (FastAPI + uvicorn), Abhängigkeiten wie in README: ``uv sync --group web``
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY ecu ./ecu
RUN uv sync --frozen --group web --no-editable

FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV="/app/.venv"
COPY --from=builder /app/.venv /app/.venv
EXPOSE 8000
CMD ["uvicorn", "ecu.ui.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
