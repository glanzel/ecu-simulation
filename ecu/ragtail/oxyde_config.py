"""Oxyde-Konfiguration für Ragtail (CLI und ``cms.lifespan``)."""
from __future__ import annotations

import os
from pathlib import Path

from oxyde.migrations.utils import detect_dialect

BASE_DIR = Path(__file__).resolve().parent

DATABASES = {
    "default": os.environ.get(
        "RAGTAIL_DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'data' / 'ragtail.db'}",
    ),
}

MODELS = ["ecu.ragtail.pages", "ragtail.models"]

MIGRATIONS_DIR = "migrations"

DIALECT = detect_dialect(DATABASES["default"])
