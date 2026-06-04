"""
FastAPI-Einstieg: ``import pyjsx.auto_setup`` muss vor Imports aus ``.px``-Modulen stehen.
"""

from __future__ import annotations

from pathlib import Path

import pyjsx.auto_setup  # noqa: E402, F401 — registriert Import-Hook für ``.px``

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from oxyde import db

from ecu.cms.menu import menu_links
from ecu.cms.models import DB_URL
from ecu.cms.setup import ensure_cms_dirs, setup_cms
from ecu.logic.observations import BOUNDARY_KEYS, MONTHS_PER_YEAR
from ecu.simulation.config import default_config
from ecu.simulation.report_aggregates import yearly_ecu_summaries, warmup_diagnostic_table_rows
from ecu.simulation.run_params import RunParams, WebRunFormFields, optional_query_int
from ecu.simulation.simulation import run_simulation
from ecu.ui.web.chart_payload import chart_data_json_for_report
from ecu.ui.web.simulation_page import simulation_page
from ecu.ui.web.view_model import build_boundary_sections

ensure_cms_dirs()
app = FastAPI(title="ECU Simulation", docs_url=None, redoc_url=None, lifespan=db.lifespan(default=DB_URL))

_static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
setup_cms(app)


@app.get("/", response_class=RedirectResponse)
async def index() -> RedirectResponse:
    return RedirectResponse(url="/simulation", status_code=302)


@app.get("/report", response_class=RedirectResponse)
async def report_redirect(request: Request) -> RedirectResponse:
    qs = request.url.query
    target = "/simulation" + (f"?{qs}" if qs else "")
    return RedirectResponse(url=target, status_code=301)


@app.get("/simulation", response_class=HTMLResponse)
async def simulation(  # HTML: ``ecu.ui.web.simulation_page.simulation_page``
    ecumenge_ziel_J: float | None = Query(None),
    periods: int = Query(5, ge=1, le=500),
    growth: str | None = Query(None),
    start_demand: str | None = Query(None),
    demand_noise_std: float | None = Query(None),
    epsilon_noise_std: float | None = Query(None),
    seed: str | None = Query(None),
    consumption_budget: str | None = Query(None),
    price_max_bundle_scale_pct: float | None = Query(None),
    price_elasticity_warmup_months: int | None = Query(None, ge=0, le=240),
) -> HTMLResponse:
    params = RunParams.from_web_query(
        ecumenge_ziel_J=ecumenge_ziel_J,
        periods=periods,
        growth=growth,
        start_demand=start_demand,
        demand_noise_std=demand_noise_std,
        epsilon_noise_std=epsilon_noise_std,
        seed=optional_query_int(seed),
        consumption_budget=consumption_budget,
        price_max_bundle_scale_pct=price_max_bundle_scale_pct,
        price_elasticity_warmup_months=price_elasticity_warmup_months,
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
    page = simulation_page(
        sections=sections,
        yearly_ecu=yearly_ecu_summaries(results),
        ecumenge_ziel_J=last.ecumenge_ziel_J,
        ecumenge_J=last.ecumenge_J,
        periods_years=params.periods_years,
        n_months=len(results),
        budget_method=cfg.consumption_budget_method.value,
        growth_by_boundary=growth_rows,
        start_demand_by_boundary=sd_rows,
        demand_noise_std=cfg.demand_at_reference_price_log_noise_std,
        epsilon_noise_std=cfg.epsilon_log_noise_std,
        seed=cfg.random_seed,
        chart_data_json=chart_data_json_for_report(results),
        setup_form=WebRunFormFields.from_run(params, cfg, growth_d),
        warmup_diag_rows=warmup_diagnostic_table_rows(results),
        nav_links=await menu_links(),
    )
    return HTMLResponse(
        str(page),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
