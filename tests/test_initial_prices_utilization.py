"""Start-Rohpreise aus Auslastungs-Proxy (gleiche Gewichte)."""

from __future__ import annotations

from ecu.logic.initial_prices import initial_weights_uniform, prices_from_weights, raw_initial_shadow_prices_from_utilization
from ecu.logic.observations import BOUNDARY_KEYS
from ecu.simulation.simulation import build_vej_ziel_bundle


def test_raw_initial_matches_weights_when_uniform_utilization() -> None:
    vej_ziel = build_vej_ziel_bundle()
    e_soll = 1200.0
    u = {k: 0.5 for k in BOUNDARY_KEYS}
    w = initial_weights_uniform(len(BOUNDARY_KEYS))
    raw_u = raw_initial_shadow_prices_from_utilization(vej_ziel, e_soll, u, w)
    raw_w = prices_from_weights(vej_ziel, e_soll, w)
    for k in BOUNDARY_KEYS:
        assert abs(raw_u[k] - raw_w[k]) < 1e-9, (k, raw_u[k], raw_w[k])


def test_ecumenge_J_not_below_ecumenge_ziel_when_overloaded_start() -> None:
    from ecu.simulation.config import SimulationConfig
    from ecu.simulation.simulation import ecumenge_J_from_start, run_simulation

    cfg = SimulationConfig(ecumenge_ziel_J=100.0, random_seed=0, start_demand_of_vej={k: 1.2 for k in BOUNDARY_KEYS})
    frac = cfg.resolved_start_demand()
    ist = ecumenge_J_from_start(frac, cfg.ecumenge_ziel_J)
    assert ist >= cfg.ecumenge_ziel_J
    results = run_simulation(cfg, months=1)
    assert results[0].ecumenge_J == ist
    assert results[0].ecumenge_T == ist / 12.0
