"""
FastAPI-Einstieg: ``import pyjsx.auto_setup`` muss vor Imports aus ``.px``-Modulen stehen.
"""

from __future__ import annotations

from pathlib import Path

import pyjsx.auto_setup  # noqa: E402, F401 — registriert Import-Hook für ``.px``

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ecu.logic.observations import BOUNDARY_KEYS, MONTHS_PER_YEAR
from ecu.simulation.config import default_config
from ecu.simulation.report_aggregates import yearly_ecu_summaries
from ecu.simulation.run_params import RunParams
from ecu.simulation.simulation import run_simulation
from ecu.ui.web.home import home_page
from ecu.ui.web.report import report_page
from ecu.ui.web.view_model import build_boundary_sections

app = FastAPI(title="ECU Simulation", docs_url=None, redoc_url=None)

_static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


def _example_links() -> list[tuple[str, str]]:
    examples: list[tuple[str, RunParams]] = [
        ("1 Jahr, Seed 1", RunParams.from_web_query(periods=1, seed=1)),
        ("5 Jahre, Standard", RunParams.from_web_query(periods=5)),
        ("2 Jahre, CO₂ Index 102", RunParams.from_web_query(periods=2, growth="102|100|100", seed=42)),
        (
            "Alle Parameter (Beispiel)",
            RunParams.from_web_query(
                ecu=95_000.0,
                periods=3,
                growth="101|100|100.5",
                d0_fraction="40|45|50",
                demand_noise_std=0.25,
                epsilon_noise_std=0.0,
                seed=42,
                consumption_budget="lagrange",
            ),
        ),
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
    d0_fraction: str | None = Query(None),
    demand_noise_std: float | None = Query(None),
    epsilon_noise_std: float | None = Query(None),
    seed: int | None = Query(None),
    consumption_budget: str | None = Query(None),
    price_max_scale_pct: float | None = Query(None),
) -> HTMLResponse:
    params = RunParams.from_web_query(
        ecu=ecu,
        periods=periods,
        growth=growth,
        d0_fraction=d0_fraction,
        demand_noise_std=demand_noise_std,
        epsilon_noise_std=epsilon_noise_std,
        seed=seed,
        consumption_budget=consumption_budget,
        price_max_scale_pct=price_max_scale_pct,
    )
    cfg = default_config()
    try:
        params.apply_to_config(cfg)
    except ValueError as e:
        return HTMLResponse(f"<pre>Fehler: {e}</pre>", status_code=400)
    try:
        growth_d = params.growth_per_boundary()
    except ValueError as e:
        return HTMLResponse(f"<pre>Fehler: {e}</pre>", status_code=400)
    months = params.periods_years * MONTHS_PER_YEAR
    results = run_simulation(cfg, months, demand_growth_per_year=growth_d)
    if not results:
        return HTMLResponse("<p>Keine Ergebnisse.</p>")
    sections = build_boundary_sections(results)
    last = results[-1]
    growth_rows = [(k, growth_d[k]) for k in BOUNDARY_KEYS]
    d0_res = cfg.resolved_d0_fraction()
    d0_rows = [(k, d0_res[k]) for k in BOUNDARY_KEYS]
    page = report_page(
        sections=sections,
        yearly_ecu=yearly_ecu_summaries(results),
        ecu_per_year=last.ecu_per_year,
        periods_years=params.periods_years,
        n_months=len(results),
        budget_method=cfg.consumption_budget_method.value,
        growth_by_boundary=growth_rows,
        d0_by_boundary=d0_rows,
        demand_noise_std=cfg.demand_at_reference_price_log_noise_std,
        epsilon_noise_std=cfg.epsilon_log_noise_std,
        seed=cfg.random_seed,
    )
    return HTMLResponse(
        str(page),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
