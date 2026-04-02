"""
FastAPI-Einstieg: ``import pyjsx.auto_setup`` muss vor Imports aus ``.px``-Modulen stehen.
"""

from __future__ import annotations

from pathlib import Path

import pyjsx.auto_setup  # noqa: E402, F401 — registriert Import-Hook für ``.px``

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ecu_simulation.logic.observations import BOUNDARY_KEYS, MONTHS_PER_YEAR
from ecu_simulation.simulation.config import default_config
from ecu_simulation.simulation.run_params import RunParams
from ecu_simulation.simulation.simulation import run_simulation
from ecu_simulation.ui.web.home import home_page
from ecu_simulation.ui.web.report import report_page
from ecu_simulation.ui.web.view_model import build_boundary_sections

app = FastAPI(title="ECU Simulation", docs_url=None, redoc_url=None)

_static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


def _example_links() -> list[tuple[str, str]]:
    examples: list[tuple[str, RunParams]] = [
        ("1 Jahr, Seed 1", RunParams.from_web_query(periods=1, seed=1)),
        ("5 Jahre, Standard", RunParams.from_web_query(periods=5)),
        ("2 Jahre, CO₂-Wachstum 1.02", RunParams.from_web_query(periods=2, growth="1.02,1,1", seed=42)),
    ]
    return [(label, f"/report?{p.to_url_query()}") for label, p in examples]


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    intro = (
        "Simulation mit denselben Parametern wie die CLI. "
        "Parameter werden als GET-Query übergeben (siehe `/report`)."
    )
    page = home_page(
        "ECU-Simulation",
        intro,
        _example_links(),
    )
    return HTMLResponse(str(page))


@app.get("/report", response_class=HTMLResponse)
def report(
    ecu: float | None = Query(None),
    periods: int = Query(5, ge=1, le=500),
    growth: str | None = Query(None),
    demand_noise_std: float | None = Query(None),
    epsilon_noise_std: float | None = Query(None),
    seed: int | None = Query(None),
    consumption_budget: str | None = Query(None),
) -> HTMLResponse:
    params = RunParams.from_web_query(
        ecu=ecu,
        periods=periods,
        growth=growth,
        demand_noise_std=demand_noise_std,
        epsilon_noise_std=epsilon_noise_std,
        seed=seed,
        consumption_budget=consumption_budget,
    )
    cfg = default_config()
    params.apply_to_config(cfg)
    try:
        growth_d = params.growth_per_boundary()
    except ValueError as e:
        return HTMLResponse(f"<pre>Fehler: {e}</pre>", status_code=400)
    months = params.periods_years * MONTHS_PER_YEAR
    results = run_simulation(cfg, months, demand_growth_per_period=growth_d)
    if not results:
        return HTMLResponse("<p>Keine Ergebnisse.</p>")
    sections = build_boundary_sections(results)
    last = results[-1]
    growth_rows = [(k, growth_d[k]) for k in BOUNDARY_KEYS]
    page = report_page(
        sections=sections,
        ecu_floor=last.ecu_floor,
        periods_years=params.periods_years,
        n_months=len(results),
        budget_method=cfg.consumption_budget_method.value,
        growth_by_boundary=growth_rows,
        demand_noise_std=cfg.demand_at_reference_price_log_noise_std,
        epsilon_noise_std=cfg.epsilon_log_noise_std,
        seed=cfg.random_seed,
    )
    return HTMLResponse(
        str(page),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
