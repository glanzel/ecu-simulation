"""Startpreise ``p = w·ecumenge/vej_ist`` (Jahres-Referenz-vej_ist = f·vej_ziel); bei f=1 wie ``prices_from_weights``."""

from __future__ import annotations

from logic.initial_prices import initial_weights_uniform, prices_from_weights
from logic.observations import BOUNDARY_KEYS
from logic.prices import initial_shadow_prices_for_ecu
from simulation.simulation import build_vej_ziel_bundle


def test_initial_shadow_matches_prices_from_weights_when_ref_vej_ist_equals_vej_ziel() -> None:
    vej_ziel = build_vej_ziel_bundle()
    e_soll = 1200.0
    f_one = {k: 1.0 for k in BOUNDARY_KEYS}
    w = initial_weights_uniform(len(BOUNDARY_KEYS))
    p_init = initial_shadow_prices_for_ecu(vej_ziel, f_one, e_soll)
    p_w = prices_from_weights(vej_ziel, e_soll, w)
    for k in BOUNDARY_KEYS:
        assert abs(p_init[k] - p_w[k]) < 1e-9, (k, p_init[k], p_w[k])


def test_ecumenge_J_not_below_ecumenge_ziel_when_overloaded_start() -> None:
    from simulation.config import SimulationConfig
    from simulation.simulation import ecumenge_J_from_start, run_simulation

    cfg = SimulationConfig(ecumenge_ziel_J=100.0, random_seed=0, start_demand_of_vej={k: 1.2 for k in BOUNDARY_KEYS})
    frac = cfg.resolved_start_demand()
    ist = ecumenge_J_from_start(frac, cfg.ecumenge_ziel_J)
    assert ist >= cfg.ecumenge_ziel_J
    results = run_simulation(cfg, months=1)
    assert results[0].ecumenge_J == ist
    assert results[0].ecumenge_T == ist / 12.0
