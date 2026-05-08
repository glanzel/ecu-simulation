"""
Preislogik: zwei getrennte Prüfgruppen.

**A — ECU-weicher Pfad (Jahressoll effektiv)**  
Ratchet auf ``ecumenge_ziel_sim_J`` / Monatsdeckel; Nutzungs-Klemme auf Rohpreise wie im Warmup,
danach ``Σ p·VEJ`` nur schrittweise (± ``p`` %/Periode) Richtung effektivem Budget.

**B — Rohpreise je Grenze**  
- Vor ``price_elasticity_warmup_months``: keine Elastizität (nur Bump in ``_raw_shadow_prices``).
- Ab Warmup: OLS-η möglich (kein Zwei-Punkt-Fallback).
- Bandformel ``r_k`` in den ersten ``price_elasticity_warmup_months`` Monaten (bei ``max_pct > 0``)
  direkt in ``advance_shadow_prices`` (Warmup-Preispfad, ohne ``Σ p·VEJ-Ziel``-Normierung); sonst nur
  in Tests über ``_clamp_shadow_prices_vs_last_by_utilization_share`` isoliert.
"""

from __future__ import annotations

from unittest import mock

import pytest

from ecu.logic.observations import (
    BOUNDARY_KEYS,
    DAYS_PER_MONTH,
    ConsumptionInterval,
    ConsumptionTimeline,
    MONTHS_PER_YEAR,
)
from ecu.logic.price_config import PriceConfig
from ecu.logic.prices import (
    _clamp_shadow_prices_vs_last_by_utilization_share,
    _implied_elasticity_for_boundary,
    _raw_shadow_prices_from_timeline,
    advance_shadow_prices,
    bundle_value,
    initial_shadow_prices_for_ecu,
    mean_utilization_soft_path_threshold,
    ratchet_ecumenge_ziel_sim_J,
    scale_percentual_to_ecu,
)
from ecu.simulation.simulation import build_vej_ziel_bundle, vet_soll_from_vej_ziel


def test_mean_u_2_2_exceeds_soft_path_threshold_for_p_1():
    """Gruppe A: Schwelle 1+p/100 bei p=1; mean_u=2,2 liegt darüber."""
    p = 1.0
    assert mean_utilization_soft_path_threshold(p) == pytest.approx(1.01)
    assert 2.2 > mean_utilization_soft_path_threshold(p)


def test_ratchet_ecumenge_ziel_sim_J_one_percent_floor():
    """Gruppe A: Ratchet auf effektives Jahres-Ziel ``ecumenge_ziel_sim_J``."""
    cfg_soll = 100_000.0
    assert ratchet_ecumenge_ziel_sim_J(150_000.0, cfg_soll, 1.0) == pytest.approx(148_500.0)
    assert ratchet_ecumenge_ziel_sim_J(102_000.0, cfg_soll, 1.0) == pytest.approx(100_980.0)
    assert ratchet_ecumenge_ziel_sim_J(100_000.0, cfg_soll, 1.0) == pytest.approx(100_000.0)


def test_advance_shadow_prices_soft_ecu_path_ratchet_and_bundle():
    """Gruppe A: weicher Pfad — Ratchet −1 %; ``Σ p·VEJ`` nur schrittweise Richtung effektivem Soll (±p %/Periode)."""
    vej_ziel = build_vej_ziel_bundle()
    vet_soll = vet_soll_from_vej_ziel(vej_ziel)
    frac = {k: 1.0 for k in BOUNDARY_KEYS}
    ecu_cfg = 100_000.0
    ecu_start_effective = 150_000.0
    p0 = initial_shadow_prices_for_ecu(vej_ziel, ecu_cfg, frac)
    vej_ist = {k: 2.2 * vet_soll[k] for k in BOUNDARY_KEYS}
    pc = PriceConfig(
        max_shadow_bundle_scale_pct_per_period=1.0,
        price_elasticity_warmup_months=1,
    )
    tl = ConsumptionTimeline(
        ecumenge_ziel_J=ecu_cfg,
        price_config=pc,
        ecumenge_ziel_J_konfig=ecu_cfg,
        ecumenge_ziel_sim_J=ecu_start_effective,
    )
    tl.append(ConsumptionInterval.from_observation(1, DAYS_PER_MONTH, p0, vej_ist, vet_soll))
    bundle_prev = bundle_value(p0, vej_ziel)
    advance_shadow_prices(tl, vej_ziel, frac)
    expected_effective = ratchet_ecumenge_ziel_sim_J(ecu_start_effective, ecu_cfg, 1.0)
    assert tl.ecumenge_ziel_sim_J == pytest.approx(expected_effective)
    assert tl.prices_for_next_consumption is not None
    bundle = bundle_value(tl.prices_for_next_consumption, vej_ziel)
    half = pc.max_shadow_bundle_scale_pct_per_period / 100.0
    assert bundle_prev * (1.0 - half) - 1e-6 <= bundle <= bundle_prev * (1.0 + half) + 1e-6
    prices_last = {k: p0[k] for k in BOUNDARY_KEYS}
    u_by = {k: vej_ist[k] / vet_soll[k] for k in BOUNDARY_KEYS}
    raw = _raw_shadow_prices_from_timeline(tl)
    clamped = _clamp_shadow_prices_vs_last_by_utilization_share(raw, prices_last, u_by, 2.2, pc.max_shadow_bundle_scale_pct_per_period)
    expected_bundle = bundle_value(
        scale_percentual_to_ecu(clamped, vej_ziel, expected_effective, pc.max_shadow_bundle_scale_pct_per_period, bundle_prev),
        vej_ziel,
    )
    assert bundle == pytest.approx(expected_bundle, abs=1e-3)
    cap = tl.ecumenge_T_override
    assert cap is not None
    assert cap == pytest.approx(expected_effective / float(MONTHS_PER_YEAR))


def test_utilization_share_relative_half_band_formula():
    """Gruppe B: Halbspanne ``(u_k·p)/(mean_u·100)`` — Beispiel 0,65 / 2,2 / 100 ≈ 0,295 %."""
    assert (0.65 * 1.0) / (2.2 * 100.0) == pytest.approx(0.65 / 220.0)
    pl = {k: 100.0 for k in BOUNDARY_KEYS}
    u_by = {k: 2.39375 for k in BOUNDARY_KEYS}
    u_by["aerosol"] = 0.65
    mean_u = sum(u_by[k] for k in BOUNDARY_KEYS) / float(len(BOUNDARY_KEYS))
    assert mean_u == pytest.approx(2.2, abs=1e-9)
    raw = dict(pl)
    raw["aerosol"] = 200.0
    out = _clamp_shadow_prices_vs_last_by_utilization_share(raw, pl, u_by, mean_u, 1.0)
    r_a = (0.65 * 1.0) / (mean_u * 100.0)
    assert out["aerosol"] == pytest.approx(100.0 * (1.0 + r_a))


def test_raw_prices_warmup_overshoot_then_utilization_clamp_on_raw():
    """Gruppe B: Bump 1,08 auf eine Grenze, danach Hilfsklemme ``_clamp_shadow…`` wie in isolierter Nachbearbeitung."""
    vej_ziel = build_vej_ziel_bundle()
    vet_soll = vet_soll_from_vej_ziel(vej_ziel)
    frac = {k: 0.5 for k in BOUNDARY_KEYS}
    ecu_cfg = 100_000.0
    p0 = initial_shadow_prices_for_ecu(vej_ziel, ecu_cfg, frac)
    pc = PriceConfig(
        max_shadow_bundle_scale_pct_per_period=1.0,
        price_elasticity_warmup_months=5,
        price_bump=1.08,
    )
    tl = ConsumptionTimeline(ecumenge_ziel_J=ecu_cfg, price_config=pc)
    k0 = BOUNDARY_KEYS[0]
    for m in range(1, 4):
        c = {k: 0.5 * vet_soll[k] for k in BOUNDARY_KEYS}
        tl.append(ConsumptionInterval.from_observation(m, DAYS_PER_MONTH, p0, c, vet_soll))
        p0 = dict(tl.last.shadow_prices_map())
    c_last = {k: 0.5 * vet_soll[k] for k in BOUNDARY_KEYS}
    c_last[k0] = 1.2 * vet_soll[k0]
    tl.append(ConsumptionInterval.from_observation(4, DAYS_PER_MONTH, p0, c_last, vet_soll))
    raw = _raw_shadow_prices_from_timeline(tl)
    last_iv = tl.last
    vet_last = {k: last_iv.vet_soll_for(k) for k in BOUNDARY_KEYS}
    prices_last = {k: last_iv.price_for(k) for k in BOUNDARY_KEYS}
    u_by = {k: (c_last[k] / vet_last[k]) if vet_last[k] > 0.0 else 0.0 for k in BOUNDARY_KEYS}
    mean_u = sum(u_by[k] for k in BOUNDARY_KEYS) / float(len(BOUNDARY_KEYS))
    raw_c = _clamp_shadow_prices_vs_last_by_utilization_share(raw, prices_last, u_by, mean_u, 1.0)
    p_last_k0 = prices_last[k0]
    bump_eff = min(1.08, 1.0 + 2.0 * 1.0 / 100.0)
    assert raw_c[k0] == pytest.approx(p_last_k0 * bump_eff)


def test_elasticity_not_called_before_warmup_months():
    """Gruppe B: während Warmup kein Elastizitätsaufruf."""
    vej_ziel = build_vej_ziel_bundle()
    vet_soll = vet_soll_from_vej_ziel(vej_ziel)
    frac = {k: 0.5 for k in BOUNDARY_KEYS}
    ecu_cfg = 100_000.0
    p0 = initial_shadow_prices_for_ecu(vej_ziel, ecu_cfg, frac)
    pc = PriceConfig(price_elasticity_warmup_months=5, max_shadow_bundle_scale_pct_per_period=1.0)
    tl = ConsumptionTimeline(ecumenge_ziel_J=ecu_cfg, price_config=pc)
    for m in range(1, 4):
        vej_ist = {k: 0.5 * vet_soll[k] for k in BOUNDARY_KEYS}
        tl.append(ConsumptionInterval.from_observation(m, DAYS_PER_MONTH, p0, vej_ist, vet_soll))
        p0 = dict(tl.last.shadow_prices_map())
    c_last = {k: 1.1 * vet_soll[k] for k in BOUNDARY_KEYS}
    tl.append(ConsumptionInterval.from_observation(4, DAYS_PER_MONTH, p0, c_last, vet_soll))
    with mock.patch("ecu.logic.prices._implied_elasticity_for_boundary") as spy:
        _raw_shadow_prices_from_timeline(tl)
    assert spy.call_count == 0


def test_warmup_price_path_clamped_only_no_scale_to_ecu():
    """Warmup: nur Klemme r_k + Ratchet; ``Σ p·VEJ-Ziel`` wird nicht auf ``ecumenge_ziel_sim_J`` gezwungen."""
    vej_ziel = build_vej_ziel_bundle()
    vet_soll = vet_soll_from_vej_ziel(vej_ziel)
    frac = {k: 1.0 for k in BOUNDARY_KEYS}
    ecu_cfg = 100_000.0
    ecu_start_effective = 150_000.0
    p0 = initial_shadow_prices_for_ecu(vej_ziel, ecu_cfg, frac)
    vej_ist = {k: 2.2 * vet_soll[k] for k in BOUNDARY_KEYS}
    pc = PriceConfig(max_shadow_bundle_scale_pct_per_period=1.0, price_elasticity_warmup_months=5)
    tl = ConsumptionTimeline(
        ecumenge_ziel_J=ecu_cfg,
        price_config=pc,
        ecumenge_ziel_J_konfig=ecu_cfg,
        ecumenge_ziel_sim_J=ecu_start_effective,
    )
    tl.append(ConsumptionInterval.from_observation(1, DAYS_PER_MONTH, p0, vej_ist, vet_soll))
    advance_shadow_prices(tl, vej_ziel, frac)
    expected_ratchet = ratchet_ecumenge_ziel_sim_J(ecu_start_effective, ecu_cfg, 1.0)
    assert tl.ecumenge_ziel_sim_J == pytest.approx(expected_ratchet)
    assert tl.warmup_diag_sum_p_vet_soll_monthly is not None
    assert tl.warmup_diag_ecumenge_ziel_sim_monthly == pytest.approx(expected_ratchet / float(MONTHS_PER_YEAR))
    p = tl.prices_for_next_consumption
    assert p is not None
    bv = bundle_value(p, vej_ziel)
    assert abs(bv - expected_ratchet) > 1.0
    assert tl.ecumenge_T_override is not None


def test_elasticity_called_after_warmup_when_overshoot():
    """Gruppe B: nach Warmup wird Elastizität pro Grenze versucht (Aufruf je Grenze mit Überschreitung)."""
    vej_ziel = build_vej_ziel_bundle()
    vet_soll = vet_soll_from_vej_ziel(vej_ziel)
    frac = {k: 0.5 for k in BOUNDARY_KEYS}
    ecu_cfg = 100_000.0
    p0 = initial_shadow_prices_for_ecu(vej_ziel, ecu_cfg, frac)
    pc = PriceConfig(
        price_elasticity_warmup_months=5,
        max_shadow_bundle_scale_pct_per_period=1.0,
        price_elasticity_history_lookback=12,
    )
    tl = ConsumptionTimeline(ecumenge_ziel_J=ecu_cfg, price_config=pc)
    for m in range(1, 6):
        vej_ist = {k: 0.5 * vet_soll[k] for k in BOUNDARY_KEYS}
        tl.append(ConsumptionInterval.from_observation(m, DAYS_PER_MONTH, p0, vej_ist, vet_soll))
        p0 = {k: max(1e-12, tl.last.price_for(k) * (1.002 if k == BOUNDARY_KEYS[0] else 1.0)) for k in BOUNDARY_KEYS}
    c_last = {k: 1.15 * vet_soll[k] for k in BOUNDARY_KEYS}
    tl.append(ConsumptionInterval.from_observation(6, DAYS_PER_MONTH, p0, c_last, vet_soll))
    with mock.patch("ecu.logic.prices._implied_elasticity_for_boundary", wraps=_implied_elasticity_for_boundary) as spy:
        _raw_shadow_prices_from_timeline(tl)
    assert spy.call_count == len(BOUNDARY_KEYS)
