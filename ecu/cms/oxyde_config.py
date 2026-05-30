"""Oxyde-Konfiguration — Migrationen aus diesem Verzeichnis ausführen."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

MODELS = ["ecu.cms.models"]
DIALECT = "sqlite"
MIGRATIONS_DIR = "migrations"
DATABASES = {
    "default": f"sqlite:///{BASE_DIR / 'data' / 'cms.db'}",
}
