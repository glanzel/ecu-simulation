# Ragtail CMS (`cms`)

[Wagtail](https://wagtail.org/)-inspired CMS built on [Ragtail](https://github.com/glanzel/ragtail) and Oxyde — separate from the simulation in `ui.web`.

## Integration

`ui.web.app` calls `setup_ragtail(app)` (after fixed routes such as `/simulation`):

- Admin: `/admin/` (login required)
- CMS pages: hierarchical paths, e.g. `/impressum/`
- JSON API: `/api/cms/pages/{path}`, `/api/cms/menus/{slug}`
- Menu “main”: entries appear in the header navigation (simulation + CMS pages)

## Page type

`ContentPage` (`cms.pages`):

| Field | Description |
|-------|-------------|
| `title`, `slug`, `body` | `body` = Markdown/rich text in the admin |
| `live` | Publish page |

Menu **main** is created automatically on first app start (`cms.seed`) if none exists yet (site root + “Simulation” link). Add more entries in the admin under **Menus**.

## Database

**Always run Ragtail CLI commands from the repo root** — that is where `oxyde_config.py` lives, which the running app also uses (`data/ragtail.db`).

```bash
uv sync --group web
mkdir -p data
uv run ragtail-seeddb --language-code de --display-name Deutsch --noinput
uv run ragtail-createsuperuser --username admin --email admin@example.com --password secret --noinput
```

Or from the repo root: `make ragtail-seed` and `make ragtail-admin USERNAME=… EMAIL=… PASSWORD=…`

Migrations run automatically on app start via `cms.lifespan`.

In the **Docker/Coolify image**, `scripts/docker-entrypoint.sh` only creates the data directory; schema migration happens on the first request via the lifespan. **`uv`** is available in the image at `/usr/local/bin/uv` (project at `/app`, venv at `/app/.venv`).

Ragtail CLI **in a running container** (working directory same as locally: repo root `/app`):

```bash
docker exec -it <container> sh
uv run ragtail-seeddb --language-code de --display-name Deutsch --noinput
uv run ragtail-createsuperuser --username admin --email admin@example.com --password secret --noinput
```

One-off in a fresh container without a running server:

```bash
docker run --rm -it ecu-simulation:latest sh -c \
  'uv run ragtail-seeddb --language-code de --display-name Deutsch --noinput'
```

Add further locales (e.g. English) afterwards in the admin under **Locales**, or run `ragtail-seeddb`/`ragtail-initdb` again per Ragtail docs — the simulation UI (`/en/simulation`) independently uses `ui/web/locales/en.json`.

## Environment variables

- `RAGTAIL_SECRET_KEY` — session secret for `/admin/`
- `RAGTAIL_DATABASE_URL` — optional, default: SQLite at `data/ragtail.db`
