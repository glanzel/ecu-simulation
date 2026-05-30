# ECU-Simulation — Kurzbefehle (Repo-Root, siehe README.md)
UV ?= uv
IMAGE ?= ecu-simulation:latest
PORT ?= 8000
WEB_DIR := ecu/ui/web

.PHONY: install test watch container run

install:
	$(UV) sync --all-groups
	cd $(WEB_DIR) && npm install

test:
	$(UV) run pytest tests/ -v

watch:
	$(UV) run uvicorn ecu.ui.web.app:app --reload --reload-include '*.px' --host 127.0.0.1 --port $(PORT)

container:
	docker build -t $(IMAGE) .

run:
	docker run --rm -p $(PORT):8000 $(IMAGE)
