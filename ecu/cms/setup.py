"""CMS in die Haupt-FastAPI-App einhängen (Django-App-ähnlich)."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ecu.cms.admin import admin
from ecu.cms.models import CMS_DIR
from ecu.cms.routes import MEDIA_DIR, router as cms_router

DATA_DIR = CMS_DIR / "data"


def ensure_cms_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def setup_cms(app: FastAPI) -> None:
    ensure_cms_dirs()
    app.include_router(cms_router)
    app.mount("/cms-media", StaticFiles(directory=str(MEDIA_DIR)), name="cms-media")
    app.mount("/admin", admin.app)
