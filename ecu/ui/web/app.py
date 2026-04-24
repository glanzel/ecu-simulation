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

# Beispiel-Listen (Reihenfolge = ``BOUNDARY_KEYS``): ein Eintrag pro planetarer Grenze.
_EX_G_CO2_102 = "102|" + "|".join(["100"] * 8)
_EX_START_DEMAND = "40|45|50|45|45|45|45|45|45"
_EX_G_MIX = "101|100|100.5|" + "|".join(["100"] * 6)


def _example_links() -> list[tuple[str, str]]:
    examples: list[tuple[str, RunParams]] = [
        ("1 Jahr, Seed 1", RunParams.from_web_query(periods=1, seed=1)),
        ("5 Jahre, Standard", RunParams.from_web_query(periods=5)),
        ("2 Jahre, CO₂ Index 102", RunParams.from_web_query(periods=2, growth=_EX_G_CO2_102, seed=42)),
        (
            "Alle Parameter (Beispiel)",
            RunParams.from_web_query(
                ecu=95_000.0,
                periods=3,
                growth=_EX_G_MIX,
                start_demand=_EX_START_DEMAND,
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
def report(  # HTML: ``ecu.ui.web.report.report_page``
    ecu: float | None = Query(None),
    periods: int = Query(5, ge=1, le=500),
    growth: str | None = Query(None),
    start_demand: str | None = Query(None),
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
        start_demand=start_demand,
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
    sd_res = cfg.resolved_start_demand()
    sd_rows = [(k, sd_res[k]) for k in BOUNDARY_KEYS]
    page = report_page(
        sections=sections,
        yearly_ecu=yearly_ecu_summaries(results),
        ecu_per_year=last.ecu_per_year,
        periods_years=params.periods_years,
        n_months=len(results),
        budget_method=cfg.consumption_budget_method.value,
        growth_by_boundary=growth_rows,
        start_demand_by_boundary=sd_rows,
        demand_noise_std=cfg.demand_at_reference_price_log_noise_std,
        epsilon_noise_std=cfg.epsilon_log_noise_std,
        seed=cfg.random_seed,
    )
    return HTMLResponse(
        str(page),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
