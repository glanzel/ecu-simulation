# ECU terminal simulation

Small Python model for an ecological currency (ECU) tied to three planetary-boundary control variables (CO₂, HANPP, nitrogen). Runs in the terminal only.

## Requirements

- **Python 3.10+**
- **Runtime:** standard library only (no `pip install` needed to run the CLI)
- **Tests (optional):** [pytest](https://pytest.org/) — see below

## Layout

The import package is **`ecu_sim`**. The repository root should be the directory that **contains** the `ecu_sim/` folder (with `main.py`, `config.py`, …), plus `tests/` and `pytest.ini` if you use tests.

## Run the simulation

From that repository root:

```bash
python ecu_sim/main.py
```

With options, for example:

```bash
python ecu_sim/main.py --periods 10 --growth-co2 1.02 --ecu 1.0
```

Alternative entry point:

```bash
python -m ecu_sim
```

(`ecu_sim/__main__.py` calls the same CLI.)

## Optional: tests

Create a virtual environment (recommended), then:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest tests/ -v
```

Use `pytest tests/ -s -v` if you want printed output from the tests.

## Licence

See [LICENSE](LICENSE).
