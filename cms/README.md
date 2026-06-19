# Ragtail-CMS (`cms`)

[Wagtail](https://wagtail.org/)-inspiriertes CMS auf [Ragtail](https://github.com/glanzel/ragtail) und Oxyde — getrennt von der Simulation in `ui.web`.

## Einbindung

`ui.web.app` ruft `setup_ragtail(app)` auf (nach den festen Routen wie `/simulation`):

- Admin: `/admin/` (Login erforderlich)
- CMS-Seiten: hierarchische Pfade, z. B. `/impressum/`
- JSON-API: `/api/cms/pages/{path}`, `/api/cms/menus/{slug}`
- Menü „main“: Einträge erscheinen in der Header-Navigation (Simulation + CMS-Seiten)

## Seitentyp

`ContentPage` (`cms.pages`):

| Feld | Beschreibung |
|------|--------------|
| `title`, `slug`, `body` | `body` = Markdown/Rich Text im Admin |
| `live` | Seite veröffentlichen |

Menü **main** wird beim ersten App-Start automatisch angelegt (`cms.seed`), sofern noch keins existiert (Site-Root + Link „Simulation“). Weitere Einträge im Admin unter **Menus**.

## Datenbank

**Ragtail-CLI-Befehle immer vom Repo-Root ausführen** — dort liegt `oxyde_config.py`, die auch die laufende App nutzt (`data/ragtail.db`).

```bash
uv sync --group web
mkdir -p data
uv run ragtail-seeddb --language-code de --display-name Deutsch --noinput
uv run ragtail-createsuperuser --username admin --email admin@example.com --password secret --noinput
```

Oder vom Repo-Root: `make ragtail-seed` und `make ragtail-admin USERNAME=… EMAIL=… PASSWORD=…`

Migrationen laufen beim App-Start über `cms.lifespan` automatisch.

Im **Docker-/Coolify-Image** legt `scripts/docker-entrypoint.sh` nur das Datenverzeichnis an; Schema-Migration erfolgt beim ersten Request über den Lifespan. **`uv`** ist im Image unter `/usr/local/bin/uv` verfügbar (Projekt unter `/app`, venv unter `/app/.venv`).

Ragtail-CLI **im laufenden Container** (Working Directory wie lokal: Repo-Root `/app`):

```bash
docker exec -it <container> sh
uv run ragtail-seeddb --language-code de --display-name Deutsch --noinput
uv run ragtail-createsuperuser --username admin --email admin@example.com --password secret --noinput
```

Einmalig in einem frischen Container ohne laufenden Server:

```bash
docker run --rm -it ecu-simulation:latest sh -c \
  'uv run ragtail-seeddb --language-code de --display-name Deutsch --noinput'
```

Weitere Locales (z. B. Englisch) danach im Admin unter **Locales** anlegen oder erneut `ragtail-seeddb`/`ragtail-initdb` gemäß Ragtail-Doku — die Simulations-UI (`/en/simulation`) nutzt unabhängig davon `ui/web/locales/en.json`.

## Umgebungsvariablen

- `RAGTAIL_SECRET_KEY` — Session-Geheimnis für `/admin/`
- `RAGTAIL_DATABASE_URL` — optional, Standard: SQLite unter `data/ragtail.db`
