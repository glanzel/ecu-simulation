"""
Preislogik: zwei getrennte Prüfgruppen.

**A — ECU-weicher Pfad (Jahressoll effektiv)**  
Ratchet auf ``ecumenge_ziel_sim`` / Monatsdeckel; Nutzungs-Klemme auf Rohpreise wie im Warmup,
danach ``Σ ecu_preis·BudgetJ-Ziel`` nur schrittweise (± ``p`` %/Periode) Richtung effektivem Budget.

**B — Rohpreise je Grenze**  
- Vor ``preisschritt_elastizitaet_ab``: keine Elastizität (nur Bump in ``_raw_ecu_preise``).
- Ab Warmup: OLS-η möglich (kein Zwei-Punkt-Fallback).
- Bandformel ``r_k`` in den ersten ``preisschritt_elastizitaet_ab`` Monaten (bei ``max_pct > 0``)
  direkt in ``advance_ecu_preise`` (Warmup-Preispfad, ohne ``Σ ecu_preis·BudgetJ-Ziel``-Normierung); sonst nur
  in Tests über ``_clamp_ecu_preise_vs_last_by_auslastung_share`` isoliert.
"""

from __future__ import annotations

from unittest import mock

import pytest

from logic.observations import (
    BOUNDARY_KEYS,
    DAYS_PER_MONTH,
    ConsumptionInterval,
    ConsumptionTimeline,
    MONTHS_PER_YEAR,
)
from logic.price_config import PriceConfig
from logic.prices import (
    _clamp_ecu_preise_vs_last_by_auslastung_share,
    _geschaetzte_preiselastizitaet_for_boundary,
    _raw_ecu_preise_from_timeline,
    advance_ecu_preise,
    ecumenge_kontenrahmen_wert,
    initial_ecu_preise_for_ecu,
    gesamtauslastung_soft_path_threshold,
    ratchet_ecumenge_ziel_sim,
    scale_percentual_to_ecu,
)
from simulation.simulation import build_budget_J_bundle, budget_T_from_budget_J


def test_gesamtauslastung_2_2_exceeds_soft_path_threshold_for_p_1():
    """Gruppe A: Schwelle 1+p/100 bei p=1; gesamtauslastung=2,2 liegt darüber."""
    p = 1.0
    assert gesamtauslastung_soft_path_threshold(p) == pytest.approx(1.01)
    assert 2.2 > gesamtauslastung_soft_path_threshold(p)


def test_ratchet_ecumenge_ziel_sim_one_percent_floor():
    """Gruppe A: Ratchet auf effektives Jahres-Ziel ``ecumenge_ziel_sim``."""
    cfg_soll = 100_000.0
    assert ratchet_ecumenge_ziel_sim(150_000.0, cfg_soll, 1.0) == pytest.approx(148_500.0)
    assert ratchet_ecumenge_ziel_sim(102_000.0, cfg_soll, 1.0) == pytest.approx(100_980.0)
    assert ratchet_ecumenge_ziel_sim(100_000.0, cfg_soll, 1.0) == pytest.approx(100_000.0)


def test_advance_ecu_preise_soft_ecu_path_ratchet_and_bundle():
    """Gruppe A: weicher Pfad — Ratchet −1 %; ``Σ ecu_preis·BudgetJ-Ziel`` nur schrittweise Richtung effektivem Soll (±p %/Periode)."""
    budget_J = build_budget_J_bundle()
    budget_T = budget_T_from_budget_J(budget_J)
    frac = {k: 1.0 for k in BOUNDARY_KEYS}
    ecu_cfg = 100_000.0
    ecu_start_effective = 150_000.0
    p0 = initial_ecu_preise_for_ecu(budget_J, frac, ecu_cfg)
    nutzung_T = {k: 2.2 * budget_T[k] for k in BOUNDARY_KEYS}
    pc = PriceConfig(
        price_algorithm="soft_path",
        deltagesamt_pct=1.0,
        preisschritt_elastizitaet_ab=1,
    )
    tl = ConsumptionTimeline(
        ecumenge_ziel=ecu_cfg,
        price_config=pc,
        ecumenge_ziel_konfig=ecu_cfg,
        ecumenge_ziel_sim=ecu_start_effective,
    )
    tl.append(ConsumptionInterval.from_observation(1, DAYS_PER_MONTH, p0, nutzung_T, budget_T))
    kontenrahmen_prev = ecumenge_kontenrahmen_wert(p0, budget_J)
    advance_ecu_preise(tl, budget_J, frac)
    expected_effective = ratchet_ecumenge_ziel_sim(ecu_start_effective, ecu_cfg, 1.0)
    assert tl.ecumenge_ziel_sim == pytest.approx(expected_effective)
    assert tl.ecu_preise_for_next_consumption is not None
    bundle = ecumenge_kontenrahmen_wert(tl.ecu_preise_for_next_consumption, budget_J)
    half = pc.deltagesamt_pct / 100.0
    assert kontenrahmen_prev * (1.0 - half) - 1e-6 <= bundle <= kontenrahmen_prev * (1.0 + half) + 1e-6
    ecu_preise_last = {k: p0[k] for k in BOUNDARY_KEYS}
    auslastung = {k: nutzung_T[k] / budget_T[k] for k in BOUNDARY_KEYS}
    raw = _raw_ecu_preise_from_timeline(tl)
    clamped = _clamp_ecu_preise_vs_last_by_auslastung_share(raw, ecu_preise_last, auslastung, 2.2, pc.deltagesamt_pct)
    expected_bundle = ecumenge_kontenrahmen_wert(
        scale_percentual_to_ecu(clamped, budget_J, expected_effective, pc.deltagesamt_pct, kontenrahmen_prev),
        budget_J,
    )
    assert bundle == pytest.approx(expected_bundle, abs=1e-3)
    cap = tl.ecumenge_T_override
    assert cap is not None
    assert cap == pytest.approx(expected_effective / float(MONTHS_PER_YEAR))


def test_utilization_share_relative_half_band_formula():
    """Gruppe B: Halbspanne ``(u_k·p)/(gesamtauslastung·100)`` — Beispiel 0,65 / 2,2 / 100 ≈ 0,295 %."""
    assert (0.65 * 1.0) / (2.2 * 100.0) == pytest.approx(0.65 / 220.0)
    pl = {k: 100.0 for k in BOUNDARY_KEYS}
    auslastung = {k: 2.39375 for k in BOUNDARY_KEYS}
    auslastung["aerosol"] = 0.65
    gesamtauslastung = sum(auslastung[k] for k in BOUNDARY_KEYS) / float(len(BOUNDARY_KEYS))
    assert gesamtauslastung == pytest.approx(2.2, abs=1e-9)
    raw = dict(pl)
    raw["aerosol"] = 200.0
    out = _clamp_ecu_preise_vs_last_by_auslastung_share(raw, pl, auslastung, gesamtauslastung, 1.0)
    r_a = (0.65 * 1.0) / (gesamtauslastung * 100.0)
    assert out["aerosol"] == pytest.approx(100.0 * (1.0 + r_a))


def test_raw_prices_warmup_overshoot_then_utilization_clamp_on_raw():
    """Gruppe B: Bump 1,08 auf eine Grenze, danach Hilfsklemme ``_clamp_shadow…`` wie in isolierter Nachbearbeitung."""
    budget_J = build_budget_J_bundle()
    budget_T = budget_T_from_budget_J(budget_J)
    frac = {k: 0.5 for k in BOUNDARY_KEYS}
    ecu_cfg = 100_000.0
    p0 = initial_ecu_preise_for_ecu(budget_J, frac, ecu_cfg)
    pc = PriceConfig(
        price_algorithm="soft_path",
        deltagesamt_pct=1.0,
        preisschritt_elastizitaet_ab=5,
        preis_bump=1.08,
    )
    tl = ConsumptionTimeline(ecumenge_ziel=ecu_cfg, price_config=pc)
    k0 = BOUNDARY_KEYS[0]
    for m in range(1, 4):
        c = {k: 0.5 * budget_T[k] for k in BOUNDARY_KEYS}
        tl.append(ConsumptionInterval.from_observation(m, DAYS_PER_MONTH, p0, c, budget_T))
        p0 = dict(tl.last.ecu_preise_map())
    c_last = {k: 0.5 * budget_T[k] for k in BOUNDARY_KEYS}
    c_last[k0] = 1.2 * budget_T[k0]
    tl.append(ConsumptionInterval.from_observation(4, DAYS_PER_MONTH, p0, c_last, budget_T))
    raw = _raw_ecu_preise_from_timeline(tl)
    last_iv = tl.last
    vz_monat_last = {k: last_iv.budget_T_for(k) for k in BOUNDARY_KEYS}
    ecu_preise_last = {k: last_iv.ecu_preis_for(k) for k in BOUNDARY_KEYS}
    auslastung = {k: (c_last[k] / vz_monat_last[k]) if vz_monat_last[k] > 0.0 else 0.0 for k in BOUNDARY_KEYS}
    gesamtauslastung = sum(auslastung[k] for k in BOUNDARY_KEYS) / float(len(BOUNDARY_KEYS))
    raw_c = _clamp_ecu_preise_vs_last_by_auslastung_share(raw, ecu_preise_last, auslastung, gesamtauslastung, 1.0)
    p_last_k0 = ecu_preise_last[k0]
    bump_eff = min(1.08, 1.0 + 2.0 * 1.0 / 100.0)
    assert raw_c[k0] == pytest.approx(p_last_k0 * bump_eff)


def test_elasticity_not_called_before_warmup_months():
    """Gruppe B: während Warmup kein Elastizitätsaufruf."""
    budget_J = build_budget_J_bundle()
    budget_T = budget_T_from_budget_J(budget_J)
    frac = {k: 0.5 for k in BOUNDARY_KEYS}
    ecu_cfg = 100_000.0
    p0 = initial_ecu_preise_for_ecu(budget_J, frac, ecu_cfg)
    pc = PriceConfig(price_algorithm="soft_path", preisschritt_elastizitaet_ab=5, deltagesamt_pct=1.0)
    tl = ConsumptionTimeline(ecumenge_ziel=ecu_cfg, price_config=pc)
    for m in range(1, 4):
        nutzung_T = {k: 0.5 * budget_T[k] for k in BOUNDARY_KEYS}
        tl.append(ConsumptionInterval.from_observation(m, DAYS_PER_MONTH, p0, nutzung_T, budget_T))
        p0 = dict(tl.last.ecu_preise_map())
    c_last = {k: 1.1 * budget_T[k] for k in BOUNDARY_KEYS}
    tl.append(ConsumptionInterval.from_observation(4, DAYS_PER_MONTH, p0, c_last, budget_T))
    with mock.patch("logic.prices._geschaetzte_preiselastizitaet_for_boundary") as spy:
        _raw_ecu_preise_from_timeline(tl)
    assert spy.call_count == 0


def test_warmup_price_path_clamped_only_no_scale_to_ecu():
    """Warmup: nur Klemme r_k + Ratchet; ``Σ ecu_preis·BudgetJ-Ziel`` wird nicht auf ``ecumenge_ziel_sim`` gezwungen."""
    budget_J = build_budget_J_bundle()
    budget_T = budget_T_from_budget_J(budget_J)
    frac = {k: 1.0 for k in BOUNDARY_KEYS}
    ecu_cfg = 100_000.0
    ecu_start_effective = 150_000.0
    p0 = initial_ecu_preise_for_ecu(budget_J, frac, ecu_cfg)
    nutzung_T = {k: 2.2 * budget_T[k] for k in BOUNDARY_KEYS}
    pc = PriceConfig(price_algorithm="soft_path", deltagesamt_pct=1.0, preisschritt_elastizitaet_ab=5)
    tl = ConsumptionTimeline(
        ecumenge_ziel=ecu_cfg,
        price_config=pc,
        ecumenge_ziel_konfig=ecu_cfg,
        ecumenge_ziel_sim=ecu_start_effective,
    )
    tl.append(ConsumptionInterval.from_observation(1, DAYS_PER_MONTH, p0, nutzung_T, budget_T))
    advance_ecu_preise(tl, budget_J, frac)
    expected_ratchet = ratchet_ecumenge_ziel_sim(ecu_start_effective, ecu_cfg, 1.0)
    assert tl.ecumenge_ziel_sim == pytest.approx(expected_ratchet)
    assert tl.warmup_diag_sum_ecu_preis_budget_T_monthly is not None
    assert tl.warmup_diag_ecumenge_ziel_sim_monthly == pytest.approx(expected_ratchet / float(MONTHS_PER_YEAR))
    p = tl.ecu_preise_for_next_consumption
    assert p is not None
    bv = ecumenge_kontenrahmen_wert(p, budget_J)
    assert abs(bv - expected_ratchet) > 1.0
    assert tl.ecumenge_T_override is not None


def test_elasticity_called_after_warmup_when_overshoot():
    """Gruppe B: nach Warmup wird Elastizität pro Grenze versucht (Aufruf je Grenze mit Überschreitung)."""
    budget_J = build_budget_J_bundle()
    budget_T = budget_T_from_budget_J(budget_J)
    frac = {k: 0.5 for k in BOUNDARY_KEYS}
    ecu_cfg = 100_000.0
    p0 = initial_ecu_preise_for_ecu(budget_J, frac, ecu_cfg)
    pc = PriceConfig(
        price_algorithm="soft_path",
        preisschritt_elastizitaet_ab=5,
        deltagesamt_pct=1.0,
        preiselastizitaet_history_lookback=12,
    )
    tl = ConsumptionTimeline(ecumenge_ziel=ecu_cfg, price_config=pc)
    for m in range(1, 6):
        nutzung_T = {k: 0.5 * budget_T[k] for k in BOUNDARY_KEYS}
        tl.append(ConsumptionInterval.from_observation(m, DAYS_PER_MONTH, p0, nutzung_T, budget_T))
        p0 = {k: max(1e-12, tl.last.ecu_preis_for(k) * (1.002 if k == BOUNDARY_KEYS[0] else 1.0)) for k in BOUNDARY_KEYS}
    c_last = {k: 1.15 * budget_T[k] for k in BOUNDARY_KEYS}
    tl.append(ConsumptionInterval.from_observation(6, DAYS_PER_MONTH, p0, c_last, budget_T))
    with mock.patch("logic.prices._geschaetzte_preiselastizitaet_for_boundary", wraps=_geschaetzte_preiselastizitaet_for_boundary) as spy:
        _raw_ecu_preise_from_timeline(tl)
    assert spy.call_count == len(BOUNDARY_KEYS)
