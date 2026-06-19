# ECU terminal simulation

Kleines Python-Modell zu einer ökologischen Währung (ECU) an drei planetaren Kontrollvariablen (CO₂, HANPP, Stickstoff). CLI und optional Web-Oberfläche (FastAPI).

## Voraussetzungen

- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/)** als Paketmanager (nativer Projekt-Workflow mit `pyproject.toml` und `uv.lock`, kein `pip install -r`)

## Projekt-Layout

- Python-Pakete im Repo-Root: `logic/`, `simulation/`, `cms/`, `ui/`
- Zentrale Konfiguration: `oxyde_config.py`, SQLite-Datenbank unter `data/`
- Alle folgenden Befehle gelten **im Repo-Root** (der Ordner mit `pyproject.toml`).

## Abhängigkeiten mit uv

```bash
uv sync                    # nur Basis (aktuell keine Runtime-Deps)
uv sync --group dev        # u. a. pytest
uv sync --group web        # FastAPI, uvicorn, PyJSX
uv sync --all-groups       # dev + web
```

`uv` legt standardmäßig eine **`.venv`** im Projekt an und schreibt **`uv.lock`**. Für reproduzierbare Installationen `uv.lock` versionieren.

## Simulation starten (CLI)

```bash
uv run ecu-sim --periods 5
```

Mit Seed:

```bash
uv run ecu-sim --periods 5 --seed 1
```

## Optional: Web-Oberfläche

Nach `uv sync --group web`:

```bash
uv run uvicorn ui.web.app:app --reload --reload-include '*.px'
```

**Darstellung:** [Tailwind CSS](https://tailwindcss.com/) mit [Tailwind Typography](https://github.com/tailwindlabs/tailwindcss-typography) liegt als gebaute Datei unter `ui/web/static/app.css` und wird unter `/static` ausgeliefert. Zum Neuaufbau nach Style-Änderungen: `npm run build:css` in `ui/web/`, siehe [ui/web/README.md](ui/web/README.md).

## Tests

Nach `uv sync --group dev`:

```bash
uv run pytest tests/ -v
```

Ausgaben der Tests: `uv run pytest tests/ -s -v`

## Lizenz

Siehe [LICENSE](LICENSE).
