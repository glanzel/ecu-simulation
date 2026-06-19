#!/bin/sh
set -e
mkdir -p data
exec uvicorn ui.web.app:app --host 0.0.0.0 --port "${PORT:-8000}"
