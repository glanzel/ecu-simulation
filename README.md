# ECU terminal simulation

Kleines Python-Modell zu einer ökologischen Währung (ECU) an drei planetaren Kontrollvariablen (CO₂, HANPP, Stickstoff). CLI und optional Web-Oberfläche (FastAPI).

## Voraussetzungen

- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/)** als Paketmanager (nativer Projekt-Workflow mit `pyproject.toml` und `uv.lock`, kein `pip install -r`)

## Projekt-Layout

- Importpaket: **`ecu_simulation`** (Ordner dieses Repos).
- Für `python -m ecu_simulation` muss das **Elternverzeichnis** dieses Ordners auf `PYTHONPATH` liegen (typisch: übergeordneter Ordner `texte/` mit `pytest.ini` und `tests/`).

## Abhängigkeiten mit uv

Im Verzeichnis **`ecu_simulation/`** (dort liegt `pyproject.toml`):

```bash
uv sync                    # nur Basis (aktuell keine Runtime-Deps)
uv sync --group dev        # u. a. pytest
uv sync --group web        # FastAPI, uvicorn, PyJSX
uv sync --all-groups       # dev + web
```

`uv` legt standardmäßig eine **`.venv`** im Projekt an und schreibt **`uv.lock`**. Für reproduzierbare Installationen `uv.lock` versionieren.

## Simulation starten (CLI)

Vom **Elternverzeichnis** des Pakets (z. B. `texte/`), sodass `ecu_simulation` importierbar ist:

```bash
cd /pfad/zu/texte
export PYTHONPATH=.
uv run --project ecu_simulation python -m ecu_simulation --periods 5
```

Kurzform mit einem Befehl:

```bash
PYTHONPATH=. uv run --project ecu_simulation python -m ecu_simulation --periods 5 --seed 1
```

## Optional: Web-Oberfläche

Nach `uv sync --group web`:

```bash
cd /pfad/zu/texte
export PYTHONPATH=.
uv run --project ecu_simulation uvicorn ecu_simulation.ui.web.app:app --reload --reload-include '*.px'
```

**Darstellung:** [Tailwind CSS](https://tailwindcss.com/) mit [Tailwind Typography](https://github.com/tailwindlabs/tailwindcss-typography) liegt als gebaute Datei `ui/web/static/app.css` im Repo und wird unter `/static` ausgeliefert. Zum Neuaufbau nach Style-Änderungen: `npm run build:css` in `ui/web/`, siehe [ui/web/README.md](ui/web/README.md).

## Tests

`uv sync --group dev`, dann vom Elternverzeichnis `texte/` (wegen `tests/` und `pytest.ini`):

```bash
cd /pfad/zu/texte
export PYTHONPATH=.
uv run --project ecu_simulation pytest tests/ -v
```

Ausgaben der Tests: `uv run --project ecu_simulation pytest tests/ -s -v`

## Lizenz

Siehe [LICENSE](LICENSE).
