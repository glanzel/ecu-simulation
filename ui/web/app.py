"""
FastAPI-Einstieg: ``import pyjsx.auto_setup`` muss vor Imports aus ``.px``-Modulen stehen.
"""

from __future__ import annotations

from pathlib import Path

import pyjsx.auto_setup  # noqa: E402, F401 — registriert Import-Hook für ``.px``

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from cms.locale_switch import app_locale_switch_links, simulation_public_path
from cms.menu import menu_links
from oxyde_config import DATABASES
from cms.seed import seed_main_menu
from cms.setup import cms, ensure_ragtail_dirs, setup_ragtail
from logic.observations import BOUNDARY_KEYS, MONTHS_PER_YEAR
from simulation.config import default_config
from simulation.report_aggregates import yearly_ecu_summaries, warmup_diagnostic_table_rows
from simulation.run_params import RunParams, WebRunFormFields, optional_query_int
from simulation.simulation import run_simulation
from ui.web.chart_payload import chart_data_json_for_report
from ui.web.i18n import simulation_i18n
from ui.web.simulation_page import simulation_page
from ui.web.view_model import build_boundary_sections
from ragtail.routing import get_default_locale, get_locale

ensure_ragtail_dirs()
app = FastAPI(
    title="ECU Simulation",
    docs_url=None,
    redoc_url=None,
    lifespan=cms.lifespan(startup_hook=seed_main_menu, **DATABASES),
)

_static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/report", response_class=RedirectResponse)
async def report_redirect(request: Request) -> RedirectResponse:
    qs = request.url.query
    target = "/simulation" + (f"?{qs}" if qs else "")
    return RedirectResponse(url=target, status_code=301)


async def _render_simulation(
    request: Request,
    language_code: str,
    *,
    ecumenge_ziel_J: float | None = None,
    periods: int = 5,
    growth: str | None = None,
    start_demand: str | None = None,
    demand_noise_std: float | None = None,
    epsilon_noise_std: float | None = None,
    seed: str | None = None,
    consumption_budget: str | None = None,
    price_max_bundle_scale_pct: float | None = None,
    price_elasticity_warmup_months: int | None = None,
) -> HTMLResponse:
    i18n = simulation_i18n(language_code)
    default = await get_default_locale()
    default_code = default.language_code if default else "de"
    simulation_path = simulation_public_path(language_code, default_language_code=default_code)
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
        return HTMLResponse(f"<pre>{i18n.text('errors.prefix')}: {e}</pre>", status_code=400)
    try:
        growth_d = params.growth_per_boundary()
    except ValueError as e:
        return HTMLResponse(f"<pre>{i18n.text('errors.prefix')}: {e}</pre>", status_code=400)
    months = params.periods_years * MONTHS_PER_YEAR
    results = run_simulation(cfg, months, demand_growth_per_year=growth_d)
    if not results:
        return HTMLResponse(f"<p>{i18n.text('errors.no_results')}</p>")
    sections = build_boundary_sections(results, i18n=i18n)
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
        chart_data_json=chart_data_json_for_report(results, i18n=i18n),
        setup_form=WebRunFormFields.from_run(params, cfg, growth_d),
        warmup_diag_rows=warmup_diagnostic_table_rows(results),
        nav_links=await menu_links(language_code),
        locale_links=await app_locale_switch_links(language_code=language_code, query=request.url.query),
        language_code=language_code,
        i18n=i18n,
        simulation_path=simulation_path,
    )
    return HTMLResponse(
        str(page),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/simulation", response_class=HTMLResponse)
async def simulation_default(
    request: Request,
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
    default = await get_default_locale()
    language_code = default.language_code if default else "de"
    return await _render_simulation(
        request,
        language_code,
        ecumenge_ziel_J=ecumenge_ziel_J,
        periods=periods,
        growth=growth,
        start_demand=start_demand,
        demand_noise_std=demand_noise_std,
        epsilon_noise_std=epsilon_noise_std,
        seed=seed,
        consumption_budget=consumption_budget,
        price_max_bundle_scale_pct=price_max_bundle_scale_pct,
        price_elasticity_warmup_months=price_elasticity_warmup_months,
    )


@app.get("/{language_code}/simulation", response_class=HTMLResponse)
async def simulation_localized(
    request: Request,
    language_code: str,
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
    locale = await get_locale(language_code.strip().lower())
    if locale is None:
        raise HTTPException(status_code=404, detail="Unknown locale")
    default = await get_default_locale()
    if default is not None and locale.language_code == default.language_code:
        qs = request.url.query
        target = "/simulation" + (f"?{qs}" if qs else "")
        return RedirectResponse(url=target, status_code=301)
    return await _render_simulation(
        request,
        locale.language_code,
        ecumenge_ziel_J=ecumenge_ziel_J,
        periods=periods,
        growth=growth,
        start_demand=start_demand,
        demand_noise_std=demand_noise_std,
        epsilon_noise_std=epsilon_noise_std,
        seed=seed,
        consumption_budget=consumption_budget,
        price_max_bundle_scale_pct=price_max_bundle_scale_pct,
        price_elasticity_warmup_months=price_elasticity_warmup_months,
    )


setup_ragtail(app)
