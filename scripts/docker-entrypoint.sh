#!/bin/sh
set -e
RAGTAIL_DIR="$(python -c 'from ecu.ragtail.oxyde_config import BASE_DIR; print(BASE_DIR)')"
mkdir -p "$RAGTAIL_DIR/data"
exec uvicorn ecu.ui.web.app:app --host 0.0.0.0 --port "${PORT:-8000}"
