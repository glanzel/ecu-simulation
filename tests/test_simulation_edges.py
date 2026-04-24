"""
Edge-Tests: VEJ-Konten, keine Überschreitung, Konzentration auf eine Grenze.

Ausgabe: Bei `pytest tests/ -s -v` siehst du pro Test die Tabellen je Grenze.
Ohne `-s` werden print-Ausgaben unterdrückt.
"""

from __future__ import annotations

from ecu.logic.observations import BOUNDARY_KEYS
from ecu.simulation.cli_simulation import print_boundary_tables
from ecu.simulation.config import SimulationConfig
from ecu.simulation.simulation import run_simulation


TOL = 1e-5


def _audit(title: str, results) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")
    print_boundary_tables(results)


def _assert_demand_within_vej(results) -> None:
    for r in results:
        for k in BOUNDARY_KEYS:
            assert r.consumption[k] <= r.vej[k] + TOL, (k, r.consumption[k], r.vej[k], r.period)


def test_ecuj_bundle_at_least_floor():
    """Kontenrahmen: EcuJ ≤ Σ p_i·VEJ_i (Slack erlaubt), bei überall f_i ≤ 1."""
    cfg = SimulationConfig(
        ecu_per_year=1.0,
        random_seed=1,
        start_demand_of_vej={k: 0.45 for k in BOUNDARY_KEYS},
    )
    results = run_simulation(cfg, months=2)
    _audit("test_ecuj_bundle_at_least_floor", results)
    for r in results:
        assert r.bundle_ecu + TOL >= r.ecu_per_year
    _assert_demand_within_vej(results)


def test_demand_never_exceeds_vej_default_config():
    """Standardparameter: gleichgewichtige Nachfrage bleibt unter VEJ."""
    cfg = SimulationConfig(ecu_per_year=1.0, random_seed=2)
    annual_co2 = 1.03**12
    g = {k: 1.0 for k in BOUNDARY_KEYS}
    g["co2"] = annual_co2
    results = run_simulation(cfg, months=5, demand_growth_per_year=g)
    _audit("test_demand_never_exceeds_vej_default_config", results)
    _assert_demand_within_vej(results)


def test_concentration_mostly_one_boundary():
    """Sehr wenig Basisnachfrage auf zwei Grenzen — aktive Grenze bleibt ≤ VEJ."""
    cfg = SimulationConfig(
        ecu_per_year=1.0,
        random_seed=3,
        start_demand_of_vej={
            "co2": 0.85,
            **{k: 0.001 for k in BOUNDARY_KEYS if k != "co2"},
        },
    )
    results = run_simulation(cfg, months=3)
    _audit("test_concentration_mostly_one_boundary", results)
    _assert_demand_within_vej(results)


def test_high_start_demand_still_bounded():
    """Hohe Basisnachfrage: Regler soll Preise treiben, Nachfrage ≤ VEJ."""
    cfg = SimulationConfig(
        ecu_per_year=1.0,
        random_seed=4,
        start_demand_of_vej={k: 0.95 for k in BOUNDARY_KEYS},
    )
    cfg.price.price_bump = 1.05
    results = run_simulation(cfg, months=1)
    _audit("test_high_start_demand_still_bounded", results)
    _assert_demand_within_vej(results)
