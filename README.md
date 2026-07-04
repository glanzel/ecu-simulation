# ECU terminal simulation

Small Python model for an ecological currency (ECU) across three planetary control variables (CO₂, HANPP, nitrogen). CLI and optional web UI (FastAPI).

## Prerequisites

- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/)** as package manager (native project workflow with `pyproject.toml` and `uv.lock`, no `pip install -r`)

## Project layout

- Python packages at the repo root: `logic/`, `simulation/`, `cms/`, `ui/`
- Central configuration: `oxyde_config.py`, SQLite database under `data/`
- All commands below apply **at the repo root** (the folder containing `pyproject.toml`).

## Dependencies with uv

```bash
uv sync                    # base only (currently no runtime deps)
uv sync --group dev        # includes pytest, among others
uv sync --group web        # FastAPI, uvicorn, PyJSX
uv sync --all-groups       # dev + web
```

By default, `uv` creates a **`.venv`** in the project and writes **`uv.lock`**. Commit `uv.lock` for reproducible installs.

## Run the simulation (CLI)

```bash
uv run ecu-sim --periods 5
```

With seed:

```bash
uv run ecu-sim --periods 5 --seed 1
```

## Optional: web UI

After `uv sync --group web`:

```bash
uv run uvicorn ui.web.app:app --reload --reload-include '*.px'
```

**Styling:** [Tailwind CSS](https://tailwindcss.com/) with [Tailwind Typography](https://github.com/tailwindlabs/tailwindcss-typography) is built to `ui/web/static/app.css` and served under `/static`. To rebuild after style changes: `npm run build:css` in `ui/web/`; see [ui/web/README.md](ui/web/README.md).

## Tests

After `uv sync --group dev`:

```bash
uv run pytest tests/ -v
```

Test output: `uv run pytest tests/ -s -v`

## License

See [LICENSE](LICENSE).
