#!/bin/sh
set -e
CMS_DIR="$(python -c 'from ecu.cms.models import CMS_DIR; print(CMS_DIR)')"
mkdir -p "$CMS_DIR/data" "$CMS_DIR/media"
cd "$CMS_DIR"
oxyde migrate
exec uvicorn ecu.ui.web.app:app --host 0.0.0.0 --port "${PORT:-8000}"
