"""Text-Algorithmus: QuoteT, Preisformel, Normierung, Elastikfaktor."""

from __future__ import annotations

import pytest

from logic.observations import BOUNDARY_KEYS, DAYS_PER_MONTH, ConsumptionInterval, ConsumptionTimeline
from logic.price_config import PriceConfig
from logic.prices import (
    _ecu_preise_from_quota,
    advance_ecu_preise,
    ecumenge_kontenrahmen_wert,
    scale_to_quota_budget,
)
from logic.quota import QuotaCalculator
from simulation.simulation import build_budget_J_bundle, budget_T_from_budget_J, berechne_gesamtauslastung


def test_quote_t_absenkung_steps_with_deltagesamt():
    budget_J = build_budget_J_bundle()
    budget_T = budget_T_from_budget_J(budget_J)
    nutzung_t0 = {k: 2.0 * budget_T[k] for k in BOUNDARY_KEYS}
    nutzung_T = dict(nutzung_t0)
    f = 0.02
    quota = QuotaCalculator.from_nutzung_budget(nutzung_T, budget_T, nutzung_t0, 0.01, 0.01)
    assert quota.absenkung_f == pytest.approx(f)
    for k in BOUNDARY_KEYS:
        assert quota.quote_T[k] == pytest.approx(nutzung_t0[k] * (1.0 - f) + budget_T[k] * f)


def test_quote_t_freezes_f_when_gesamtauslastung_at_one():
    budget_J = build_budget_J_bundle()
    budget_T = budget_T_from_budget_J(budget_J)
    nutzung_t0 = {k: 3.0 * budget_T[k] for k in BOUNDARY_KEYS}
    nutzung_T = {k: 1.0 * budget_T[k] for k in BOUNDARY_KEYS}
    f_prev = 0.5
    quota = QuotaCalculator.from_nutzung_budget(nutzung_T, budget_T, nutzung_t0, f_prev, 0.01)
    assert quota.absenkung is False
    assert quota.absenkung_f == f_prev
    for k in BOUNDARY_KEYS:
        assert quota.quote_T[k] == pytest.approx(nutzung_t0[k] * 0.5 + budget_T[k] * 0.5)


def test_text_path_long_run_gesamtauslastung_near_one():
    from simulation.config import SimulationConfig
    from simulation.simulation import run_simulation

    cfg = SimulationConfig()
    cfg.price.deltagesamt_pct = 1.0
    cfg.price.price_algorithm = "text"
    cfg.random_seed = 0
    cfg.demand_at_reference_price_log_noise_std = 0.0
    cfg.epsilon_log_noise_std = 0.0
    results = run_simulation(cfg, months=200)
    g_end = berechne_gesamtauslastung(results[-1].nutzung_T, results[-1].budget_T)
    assert g_end == pytest.approx(1.0, abs=0.02)


def test_delta_T_relative_to_auslastung():
    budget_J = build_budget_J_bundle()
    budget_T = budget_T_from_budget_J(budget_J)
    nutzung_T = {k: budget_T[k] for k in BOUNDARY_KEYS}
    nutzung_T["co2"] = 2.0 * budget_T["co2"]
    nutzung_t0 = {k: budget_T[k] for k in BOUNDARY_KEYS}
    nutzung_t0["co2"] = 2.0 * budget_T["co2"]
    quota = QuotaCalculator.from_nutzung_budget(nutzung_T, budget_T, nutzung_t0, 0.0, 0.1)
    assert quota.delta_T["co2"] > quota.delta_T["ozone"]


def test_scale_to_quota_budget_invariant():
    budget_J = build_budget_J_bundle()
    budget_T = budget_T_from_budget_J(budget_J)
    nutzung_T = {k: 1.1 * budget_T[k] for k in BOUNDARY_KEYS}
    nutzung_t0 = dict(nutzung_T)
    quota = QuotaCalculator.from_nutzung_budget(nutzung_T, budget_T, nutzung_t0, 0.02, 0.01)
    ecumenge_T = 10_000.0
    raw = _ecu_preise_from_quota(ecumenge_T, quota.quote_T)
    scaled = scale_to_quota_budget(raw, quota.quote_T, ecumenge_T)
    assert ecumenge_kontenrahmen_wert(scaled, quota.quote_T) == pytest.approx(ecumenge_T, rel=1e-9)


def test_text_path_sets_quota_on_timeline():
    budget_J = build_budget_J_bundle()
    budget_T = budget_T_from_budget_J(budget_J)
    frac = {k: 1.0 for k in BOUNDARY_KEYS}
    ecu_cfg = 100_000.0
    pc = PriceConfig(price_algorithm="text", deltagesamt_pct=1.0, preisschritt_elastizitaet_ab=5)
    from logic.prices import initial_ecu_preise_for_ecu

    p0 = initial_ecu_preise_for_ecu(budget_J, frac, ecu_cfg)
    nutzung_T = {k: 1.2 * budget_T[k] for k in BOUNDARY_KEYS}
    tl = ConsumptionTimeline(ecumenge_ziel=ecu_cfg, price_config=pc, ecumenge_ziel_konfig=ecu_cfg, ecumenge_ziel_sim=ecu_cfg)
    tl.append(ConsumptionInterval.from_observation(1, DAYS_PER_MONTH, p0, nutzung_T, budget_T))
    advance_ecu_preise(tl, budget_J, frac)
    assert tl.last_quota is not None
    assert tl.ecu_preise_for_next_consumption is not None
    bundle = ecumenge_kontenrahmen_wert(tl.ecu_preise_for_next_consumption, tl.last_quota.quote_T)
    assert bundle == pytest.approx(tl.ecumenge_T_override, rel=0.01)
