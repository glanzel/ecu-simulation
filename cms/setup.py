"""Ragtail in die Haupt-FastAPI-App einhängen."""
from __future__ import annotations

import os

from fastapi import FastAPI

import cms.pages  # noqa: F401 — ContentPage registrieren
from oxyde_config import BASE_DIR
from ragtail import FastAPICMS, PyJsxRenderer

DATA_DIR = BASE_DIR / "data"
SECRET_KEY = os.environ.get("RAGTAIL_SECRET_KEY", "ecu-ragtail-dev-secret-change-me")

cms = FastAPICMS(
    secret_key=SECRET_KEY,
    title="ECU CMS",
    template_engine=PyJsxRenderer(components_module="cms.templates.content_page"),
)


def ensure_ragtail_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def setup_ragtail(app: FastAPI) -> None:
    """Admin, JSON-API und öffentliche Seiten anhängen (Catch-all zuletzt)."""
    ensure_ragtail_dirs()
    cms.mount(app)
