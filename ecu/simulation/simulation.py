"""
Zeitschritt-Simulation: pro Periode zuerst Schattenpreise (``advance_shadow_prices``),
dann genau ein Konsum; eine gemeinsame ``ConsumptionTimeline`` über alle Perioden.

Schattenpreise und ECU-Logik liegen in ``logic.prices``. VEJ-Benennung: ``ecu/GLOSSAR.md``.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from ecu.logic.observations import (
    BOUNDARY_KEYS,
    DAYS_PER_MONTH,
    MONTHS_PER_YEAR,
    ConsumptionInterval,
    ConsumptionTimeline,
)
from ecu.logic.planetary_constants import ALL_BOUNDARIES, default_growth_by_key
from ecu.logic.prices import (
    advance_shadow_prices,
    bundle_value,
    exchange_rates_for_shadow_prices,
    reference_shadow_prices_for_demand,
)
from ecu.logic.vej import compute_vej
from ecu.simulation.config import SimulationConfig
from ecu.simulation.consumption_budget import (
    ConsumptionBudgetMethod,
    apply_consumption_budget,
)
from ecu.simulation.demand import consumption_quantity


@dataclass
class PeriodResult:
    period: int
    prices: dict[str, float]
    vej_ist: dict[str, float]
    """Monatlicher Ist-Verbrauch (Verschmutzungseinheiten) je Grenze nach Budgetabbildung."""
    vej_ziel: dict[str, float]
    """Langfristiges planetares Ziel je Grenze (Jahres-Obergrenze, physische Einheit/a)."""
    vet_soll: dict[str, float]
    """Kurzfristiges monatliches Soll (``vej_ziel / 12``)."""
    bundle_ecu: float
    """Σ p·VEJ-Ziel — hypothetischer Jahreswert des vollen Ziel-Bündels zu den Schattenpreisen."""
    ecu_ist_T: float
    """Verbuchte ECU im Zeitschritt T (Summe der Grenz-Spalte p·vej_ist)."""
    ecumenge_ziel_J: float
    """Konfiguriertes langfristiges Jahresziel (ECU/Jahr)."""
    ecumenge_J: float
    """Simulierte wirksame Jahresmenge am Laufstart (kann bei hoher Start-Auslastung > Ziel liegen)."""
    ecumenge_T: float
    """Im Zeitschritt T ausgegebene simulierte ECU-Menge (Budgetobergrenze für Σ p·c)."""
    mean_utilization: float
    """Mittel aus VEJ-Ist / VET-Soll über alle Grenzen (kann > 1 sein, z. B. Grenzüberschreitung)."""
    ecu_per_unit: dict[str, float]
    unit_per_ecu: dict[str, float]
    demand_at_reference_price: dict[str, float]
    consumption_timeline: ConsumptionTimeline
    """Gemeinsame, fortlaufende Timeline (bis einschließlich dieser Periode)."""
    warmup_diag_sum_p_vet_soll_monthly: float | None = None
    """Warmup: Σ p·VET-Soll (Monat) zu den gesetzten Schattenpreisen."""
    warmup_diag_ecumenge_ziel_sim_monthly: float | None = None
    """Warmup: ``ecumenge_ziel_sim_J/12`` nach ggf. Ratchet (nur Diagnose)."""


def mean_start_utilization_from_fractions(fraction_of_vej_ziel: dict[str, float]) -> float:
    """Mittel der Start-Auslastungs-Proxys (Anteil am VEJ-Ziel je Grenze)."""
    parts = [float(fraction_of_vej_ziel[k]) for k in BOUNDARY_KEYS]
    return sum(parts) / float(len(parts))


def ecumenge_J_from_start(fraction_of_vej_ziel: dict[str, float], ecumenge_ziel_J: float) -> float:
    """Simulierte wirksame Jahresmenge am Start: Ziel skaliert mit Ø-Auslastung, falls diese > 100 %."""
    u_avg = mean_start_utilization_from_fractions(fraction_of_vej_ziel)
    return ecumenge_ziel_J * max(1.0, u_avg)


def build_vej_ziel_bundle() -> dict[str, float]:
    out: dict[str, float] = {}
    for b in ALL_BOUNDARIES:
        out[b.key] = compute_vej(b.AG, b.VK, b.RZ)
    return out


def vet_soll_from_vej_ziel(vej_ziel: dict[str, float]) -> dict[str, float]:
    """Monatliches VET-Soll = VEJ-Ziel / 12 (glattes Jahr)."""
    inv = float(MONTHS_PER_YEAR)
    return {k: vej_ziel[k] / inv for k in BOUNDARY_KEYS}


def _raw_vej_ist_at_prices(
    shadow: dict[str, float],
    demand_at_reference_price: dict[str, float],
    reference_shadow_price: dict[str, float],
    price_elasticity: dict[str, float],
) -> dict[str, float]:
    out: dict[str, float] = {}
    for k in BOUNDARY_KEYS:
        out[k] = consumption_quantity(
            shadow[k],
            demand_at_reference_price[k],
            reference_shadow_price[k],
            price_elasticity[k],
        )
    return out


def run_one_period(
    period_index: int,
    timeline: ConsumptionTimeline,
    vej_ziel: dict[str, float],
    demand_at_reference_price: dict[str, float],
    reference_shadow_price: dict[str, float],
    price_elasticity: dict[str, float],
    ecumenge_ziel_J: float,
    ecumenge_J_start: float,
    budget_method: ConsumptionBudgetMethod,
    fraction_of_vej_ziel: dict[str, float],
) -> tuple[dict[str, float], dict[str, float], float, float]:
    """
    Ein Monat: zuerst ``advance_shadow_prices`` (Preise für diesen Konsum),
    dann Roh-Nachfrage, ggf. Drosselung auf monatliche ECU-Obergrenze via ``budget_method``,
    dann ein neues Intervall an der gemeinsamen Timeline.
    """
    timeline.ecumenge_ziel_J = ecumenge_ziel_J
    advance_shadow_prices(timeline, vej_ziel, fraction_of_vej_ziel)
    p = timeline.prices_for_next_consumption
    if p is None:
        raise RuntimeError(
            "advance_shadow_prices muss prices_for_next_consumption setzen."
        )
    raw_vej_ist = _raw_vej_ist_at_prices(
        p, demand_at_reference_price, reference_shadow_price, price_elasticity
    )
    if len(timeline) == 0:
        ecumenge_T = ecumenge_J_start / float(MONTHS_PER_YEAR)
    else:
        ecumenge_T = timeline.take_ecumenge_T(ecumenge_ziel_J, MONTHS_PER_YEAR)
    vej_ist = apply_consumption_budget(raw_vej_ist, p, ecumenge_T, budget_method)
    vet_soll = vet_soll_from_vej_ziel(vej_ziel)
    timeline.append(
        ConsumptionInterval.from_observation(
            period_index,
            DAYS_PER_MONTH,
            p,
            vej_ist,
            vet_soll,
            demand_at_reference_price=demand_at_reference_price,
            reference_shadow_price=reference_shadow_price,
        )
    )
    bv = bundle_value(p, vej_ziel)
    return p, vej_ist, bv, ecumenge_T


def mean_boundary_utilization(vej_ist: dict[str, float], vet_soll: dict[str, float]) -> float:
    """Durchschnitt der Auslastung pro Grenze (VEJ-Ist / VET-Soll)."""
    parts = [
        vej_ist[k] / vet_soll[k] if vet_soll[k] > 0 else 0.0
        for k in BOUNDARY_KEYS
    ]
    return sum(parts) / len(parts)


def run_simulation(
    cfg: SimulationConfig,
    months: int,
    demand_growth_per_year: dict[str, float] | None = None,
    *,
    steps_per_year: int = MONTHS_PER_YEAR,
) -> list[PeriodResult]:
    """
    months: Anzahl Zeitschritte (aktuell: ein Datenpunkt pro Monat).
    demand_growth_per_year: multiplikativer Faktor pro Grenze **pro Kalenderjahr**
    (Index/100 in CLI/Web). Pro Zeitschritt wird ``Faktor_jahr ** (1/steps_per_year)``
    auf die Referenznachfrage angewendet — über ein volles Jahr ergibt sich der Jahresfaktor.
    steps_per_year: Simulations­schritte pro Kalenderjahr (Standard 12 Monate; später z. B. 365 für täglich).
    Konsum: ``cfg.consumption_budget_method`` begrenzt ``Σ p·c`` pro Monat auf ``ecumenge_T``
    (erste Periode: ``ecumenge_J/12``, sonst Ziel/12 bzw. Override aus weichem Preispfad).
    """
    if cfg.random_seed is not None:
        random.seed(cfg.random_seed)

    if steps_per_year < 1:
        raise ValueError("steps_per_year muss mindestens 1 sein.")

    vej_ziel = build_vej_ziel_bundle()
    vet_soll = vet_soll_from_vej_ziel(vej_ziel)
    base_epsilon = cfg.resolved_epsilon()
    frac = cfg.resolved_start_demand()
    demand_at_reference_price = {k: frac[k] * vet_soll[k] for k in BOUNDARY_KEYS}
    annual = (
        demand_growth_per_year
        if demand_growth_per_year is not None
        else default_growth_by_key()
    )
    inv = float(steps_per_year)
    growth_per_period = {k: annual[k] ** (1.0 / inv) for k in BOUNDARY_KEYS}

    ecumenge_ziel_J = cfg.ecumenge_ziel_J
    ecumenge_J = ecumenge_J_from_start(frac, ecumenge_ziel_J)
    reference_shadow_price = reference_shadow_prices_for_demand(cfg, vej_ziel, ecumenge_ziel_J)

    timeline = ConsumptionTimeline(
        ecumenge_ziel_J=ecumenge_ziel_J,
        price_config=cfg.price,
        ecumenge_ziel_J_konfig=ecumenge_ziel_J,
        ecumenge_ziel_sim_J=max(ecumenge_ziel_J, ecumenge_J),
    )
    results: list[PeriodResult] = []
    demand_noise_std = cfg.demand_at_reference_price_log_noise_std
    epsilon_noise_std = cfg.epsilon_log_noise_std
    for t in range(months):
        demand_at_reference_price = {
            k: demand_at_reference_price[k] * growth_per_period[k] for k in BOUNDARY_KEYS
        }
        if demand_noise_std > 0.0:
            for k in BOUNDARY_KEYS:
                demand_at_reference_price[k] *= math.exp(
                    random.gauss(0.0, demand_noise_std)
                )
        if epsilon_noise_std > 0.0:
            price_elasticity = {
                k: base_epsilon[k] * math.exp(random.gauss(0.0, epsilon_noise_std))
                for k in BOUNDARY_KEYS
            }
        else:
            price_elasticity = dict(base_epsilon)
        p, vej_ist, bv, ecu_cap_m = run_one_period(
            t + 1,
            timeline,
            vej_ziel,
            demand_at_reference_price,
            reference_shadow_price,
            price_elasticity,
            ecumenge_ziel_J,
            ecumenge_J,
            cfg.consumption_budget_method,
            frac,
        )
        mean_u = mean_boundary_utilization(vej_ist, vet_soll)
        xr = exchange_rates_for_shadow_prices(p)
        ecu_ist_T = bundle_value(p, vej_ist)
        w_sum = timeline.warmup_diag_sum_p_vet_soll_monthly
        w_ecu_m = timeline.warmup_diag_ecumenge_ziel_sim_monthly
        timeline.warmup_diag_sum_p_vet_soll_monthly = None
        timeline.warmup_diag_ecumenge_ziel_sim_monthly = None
        results.append(
            PeriodResult(
                period=t + 1,
                prices=p,
                vej_ist=vej_ist,
                vej_ziel=vej_ziel,
                vet_soll=vet_soll,
                bundle_ecu=bv,
                ecu_ist_T=ecu_ist_T,
                ecumenge_ziel_J=ecumenge_ziel_J,
                ecumenge_J=ecumenge_J,
                ecumenge_T=ecu_cap_m,
                mean_utilization=mean_u,
                ecu_per_unit=xr.ecu_per_unit,
                unit_per_ecu=xr.unit_per_ecu,
                demand_at_reference_price=dict(demand_at_reference_price),
                consumption_timeline=timeline,
                warmup_diag_sum_p_vet_soll_monthly=w_sum,
                warmup_diag_ecumenge_ziel_sim_monthly=w_ecu_m,
            )
        )
    return results
