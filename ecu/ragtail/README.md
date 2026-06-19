# Ragtail-CMS (`ecu.ragtail`)

[Wagtail](https://wagtail.org/)-inspiriertes CMS auf [Ragtail](https://github.com/glanzel/ragtail) und Oxyde — getrennt von der Simulation in `ecu.ui.web`.

## Einbindung

`ecu.ui.web.app` ruft `setup_ragtail(app)` auf (nach den festen Routen wie `/simulation`):

- Admin: `/admin/` (Login erforderlich)
- CMS-Seiten: hierarchische Pfade, z. B. `/impressum/`
- JSON-API: `/api/cms/pages/{path}`, `/api/cms/menus/{slug}`
- Menü „main“: Einträge erscheinen in der Header-Navigation (Simulation + CMS-Seiten)

## Seitentyp

`ContentPage` (`ecu.ragtail.pages`):

| Feld | Beschreibung |
|------|--------------|
| `title`, `slug`, `body` | `body` = Markdown/Rich Text im Admin |
| `live` | Seite veröffentlichen |

Menü **main** wird beim ersten App-Start automatisch angelegt (`ecu.ragtail.seed`), sofern noch keins existiert (Site-Root + Link „Simulation“). Weitere Einträge im Admin unter **Menus**.

## Datenbank

**Ragtail-CLI-Befehle immer aus `ecu/ragtail/` ausführen** — dort liegt die `oxyde_config.py`, die auch die laufende App nutzt (`ecu/ragtail/data/ragtail.db`). Im Repo-Root gibt es keine eigene Oxyde-Konfiguration mehr.

```bash
uv sync --group web
mkdir -p ecu/ragtail/data
cd ecu/ragtail && uv run ragtail-seeddb --language-code de --display-name Deutsch --noinput
cd ecu/ragtail && uv run ragtail-createsuperuser --username admin --email admin@example.com --password secret --noinput
```

Oder vom Repo-Root: `make ragtail-seed` und `make ragtail-admin USERNAME=… EMAIL=… PASSWORD=…`

Migrationen laufen beim App-Start über `cms.lifespan` automatisch.

Im **Docker-/Coolify-Image** legt `scripts/docker-entrypoint.sh` nur das Datenverzeichnis an; Schema-Migration erfolgt beim ersten Request über den Lifespan.

## Umgebungsvariablen

- `RAGTAIL_SECRET_KEY` — Session-Geheimnis für `/admin/`
- `RAGTAIL_DATABASE_URL` — optional, Standard: SQLite unter `ecu/ragtail/data/ragtail.db`
