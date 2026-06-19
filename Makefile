# ECU-Simulation — Kurzbefehle (Repo-Root, siehe README.md)
UV ?= uv
IMAGE ?= ecu-simulation:latest
PORT ?= 8000
WEB_DIR := ui/web

.PHONY: install test watch container run ragtail-seed ragtail-admin

install:
	$(UV) sync --all-groups
	cd $(WEB_DIR) && npm install

test:
	$(UV) run pytest tests/ -v

watch:
	$(UV) run uvicorn ui.web.app:app --reload --reload-include '*.px' --host 127.0.0.1 --port $(PORT)

container:
	docker build -t $(IMAGE) .

run:
	docker run --rm -p $(PORT):8000 $(IMAGE)

ragtail-seed:
	mkdir -p data
	$(UV) run ragtail-seeddb --language-code de --display-name Deutsch --noinput

ragtail-admin:
	@test -n "$(USERNAME)" && test -n "$(EMAIL)" && test -n "$(PASSWORD)" || (echo "USERNAME, EMAIL und PASSWORD setzen, z. B. make ragtail-admin USERNAME=admin EMAIL=a@b.de PASSWORD=secret"; exit 1)
	mkdir -p data
	$(UV) run ragtail-createsuperuser --username "$(USERNAME)" --email "$(EMAIL)" --password "$(PASSWORD)" --noinput $(if $(UPDATE),--update,)
