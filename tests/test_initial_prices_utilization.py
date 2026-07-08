"""Startpreise ``p = w·ecumenge/nutzung_T`` (Jahres-Referenz-nutzung_T = f·budget_J); bei f=1 wie ``prices_from_weights``."""

from __future__ import annotations

import pytest

from logic.initial_ecu_preise import initial_weights_uniform, prices_from_weights
from logic.observations import BOUNDARY_KEYS
from logic.prices import initial_ecu_preise_for_ecu
from simulation.simulation import build_budget_J_bundle


def test_initial_shadow_matches_prices_from_weights_when_ref_nutzung_T_equals_budget_J() -> None:
    budget_J = build_budget_J_bundle()
    e_soll = 1200.0
    f_one = {k: 1.0 for k in BOUNDARY_KEYS}
    w = initial_weights_uniform(len(BOUNDARY_KEYS))
    p_init = initial_ecu_preise_for_ecu(budget_J, f_one, e_soll)
    p_w = prices_from_weights(budget_J, e_soll, w)
    for k in BOUNDARY_KEYS:
        assert abs(p_init[k] - p_w[k]) < 1e-9, (k, p_init[k], p_w[k])


def test_ecumenge_J_not_below_ecumenge_ziel_when_overloaded_start() -> None:
    from simulation.config import SimulationConfig
    from simulation.simulation import ecumenge_J_from_start, run_simulation

    cfg = SimulationConfig(ecumenge_ziel=100.0, random_seed=0, start_nutzung_anteil_budget={k: 1.2 for k in BOUNDARY_KEYS})
    budget_J = build_budget_J_bundle()
    frac = cfg.resolved_start_demand()
    ist = ecumenge_J_from_start(frac, budget_J, cfg.ecumenge_ziel)
    assert ist >= cfg.ecumenge_ziel
    results = run_simulation(cfg, months=1)
    assert results[0].ecumenge_J == ist
    assert results[0].ecumenge_T == ist / 12.0


def test_ecumenge_J_scales_with_gesamtauslastung_at_default_start() -> None:
    from logic.planetary_constants import default_start_demand_by_key
    from simulation.simulation import berechne_gesamtauslastung, budget_T_from_budget_J, ecumenge_J_from_start

    budget_J = build_budget_J_bundle()
    frac = default_start_demand_by_key()
    budget_T = budget_T_from_budget_J(budget_J)
    nutzung_T = {k: frac[k] * budget_T[k] for k in BOUNDARY_KEYS}
    ecumenge_ziel = 100_000.0
    u = berechne_gesamtauslastung(nutzung_T, budget_T)
    assert u > 1.0
    assert ecumenge_J_from_start(frac, budget_J, ecumenge_ziel) == pytest.approx(ecumenge_ziel * u)
