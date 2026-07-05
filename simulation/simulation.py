"""
Zeitschritt-Simulation: pro Periode zuerst ECU-Preise (``advance_ecu_preise``),
dann genau ein Konsum; eine gemeinsame ``ConsumptionTimeline`` über alle Perioden.

ECU-Preise und ECU-Logik liegen in ``logic.prices``. VEJ-/BudgetT: ``GLOSSAR.md``.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from logic.observations import (
    BOUNDARY_KEYS,
    DAYS_PER_MONTH,
    MONTHS_PER_YEAR,
    ConsumptionInterval,
    ConsumptionTimeline,
)
from logic.planetary_constants import ALL_BOUNDARIES, default_growth_by_key
from logic.prices import (
    advance_ecu_preise,
    ecumenge_kontenrahmen_wert,
    exchange_rates_for_ecu_preise,
    reference_ecu_preise_for_demand,
)
from logic.budget import compute_budget_J
from simulation.config import SimulationConfig
from simulation.consumption_budget import (
    ConsumptionBudgetMethod,
    apply_consumption_budget,
)
from simulation.demand import consumption_quantity


@dataclass
class PeriodResult:
    period: int
    prices: dict[str, float]
    nutzung_T: dict[str, float]
    """Monatlicher Ist-Verbrauch (Verschmutzungseinheiten) je Grenze nach Budgetabbildung."""
    budget_J: dict[str, float]
    """Langfristiges planetares Ziel je Grenze (Jahres-Obergrenze, physische Einheit/a)."""
    budget_T: dict[str, float]
    """BudgetT pro Monat (``budget_J / 12``)."""
    ecumenge_kontenrahmen: float
    """Σ ecu_preis·BudgetJ-Ziel — hypothetischer Jahreswert des vollen Ziel-Bündels zu den ECU-Preisen."""
    ecu_ist_T: float
    """Verbuchte ECU im Zeitschritt T (Summe der Grenz-Spalte p·nutzung_T)."""
    ecumenge_ziel: float
    """Konfiguriertes langfristiges Jahresziel (ECU/Jahr)."""
    ecumenge_J: float
    """Simulierte wirksame Jahresmenge am Laufstart (kann bei hoher Start-Auslastung > Ziel liegen)."""
    ecumenge_T: float
    """Im Zeitschritt T ausgegebene simulierte ECU-Menge (Budgetobergrenze für Σ p·c)."""
    gesamtauslastung: float
    """Mittel aus NutzungT / BudgetT über alle Grenzen (kann > 1 sein, z. B. Grenzüberschreitung)."""
    elastikfaktor: dict[str, float]
    """Auf die ECU-Preise dieser Periode angewendeter Elastikfaktor je Grenze (1.0 vor Preisschritt 5)."""
    ecu_per_unit: dict[str, float]
    unit_per_ecu: dict[str, float]
    demand_at_reference_price: dict[str, float]
    consumption_timeline: ConsumptionTimeline
    """Gemeinsame, fortlaufende Timeline (bis einschließlich dieser Periode)."""
    warmup_diag_sum_ecu_preis_budget_T_monthly: float | None = None
    """Warmup: Σ ecu_preis·BudgetT-Ziel zu den gesetzten ECU-Preisen."""
    warmup_diag_ecumenge_ziel_sim_monthly: float | None = None
    """Warmup: ``ecumenge_ziel_sim/12`` nach ggf. Ratchet (nur Diagnose)."""


def mean_start_utilization_from_fractions(nutzung_anteil_budget: dict[str, float]) -> float:
    """Mittel der Start-Auslastungs-Proxys (Anteil am BudgetJ je Grenze)."""
    parts = [float(nutzung_anteil_budget[k]) for k in BOUNDARY_KEYS]
    return sum(parts) / float(len(parts))


def ecumenge_J_from_start(
    nutzung_anteil_budget: dict[str, float], budget_J: dict[str, float], ecumenge_ziel: float
) -> float:
    """EcumengeJ = EcumengeZiel · Σ NutzungT0 / Σ BudgetJ (gewichtet); mindestens EcumengeZiel."""
    nutzung_sum = sum(float(nutzung_anteil_budget[k]) * float(budget_J[k]) for k in BOUNDARY_KEYS)
    budget_sum = sum(float(budget_J[k]) for k in BOUNDARY_KEYS)
    if budget_sum <= 0.0:
        return ecumenge_ziel
    return ecumenge_ziel * max(1.0, nutzung_sum / budget_sum)


def build_budget_J_bundle() -> dict[str, float]:
    out: dict[str, float] = {}
    for b in ALL_BOUNDARIES:
        out[b.key] = compute_budget_J(b.grenze, b.vk, b.regeneration)
    return out


def budget_T_from_budget_J(budget_J: dict[str, float]) -> dict[str, float]:
    """BudgetT je Grenze: ``budget_J / 12`` (glattes Jahr)."""
    inv = float(MONTHS_PER_YEAR)
    return {k: budget_J[k] / inv for k in BOUNDARY_KEYS}


def _raw_nutzung_T_at_prices(
    shadow: dict[str, float],
    demand_at_reference_price: dict[str, float],
    reference_ecu_preis: dict[str, float],
    price_elasticity: dict[str, float],
) -> dict[str, float]:
    out: dict[str, float] = {}
    for k in BOUNDARY_KEYS:
        out[k] = consumption_quantity(
            shadow[k],
            demand_at_reference_price[k],
            reference_ecu_preis[k],
            price_elasticity[k],
        )
    return out


def run_one_period(
    period_index: int,
    timeline: ConsumptionTimeline,
    budget_J: dict[str, float],
    demand_at_reference_price: dict[str, float],
    reference_ecu_preis: dict[str, float],
    price_elasticity: dict[str, float],
    ecumenge_ziel: float,
    ecumenge_J_start: float,
    budget_method: ConsumptionBudgetMethod,
    nutzung_anteil_budget: dict[str, float],
) -> tuple[dict[str, float], dict[str, float], float, float]:
    """
    Ein Monat: zuerst ``advance_ecu_preise`` (Preise für diesen Konsum),
    dann Roh-Nachfrage, ggf. Drosselung auf monatliche ECU-Obergrenze via ``budget_method``,
    dann ein neues Intervall an der gemeinsamen Timeline.
    """
    timeline.ecumenge_ziel = ecumenge_ziel
    advance_ecu_preise(timeline, budget_J, nutzung_anteil_budget)
    p = timeline.ecu_preise_for_next_consumption
    if p is None:
        raise RuntimeError(
            "advance_ecu_preise muss ecu_preise_for_next_consumption setzen."
        )
    raw_nutzung_T = _raw_nutzung_T_at_prices(
        p, demand_at_reference_price, reference_ecu_preis, price_elasticity
    )
    if len(timeline) == 0:
        ecumenge_T = ecumenge_J_start / float(MONTHS_PER_YEAR)
    else:
        ecumenge_T = timeline.take_ecumenge_T(ecumenge_ziel, MONTHS_PER_YEAR)
    nutzung_T = apply_consumption_budget(raw_nutzung_T, p, ecumenge_T, budget_method)
    budget_T = budget_T_from_budget_J(budget_J)
    timeline.append(
        ConsumptionInterval.from_observation(
            period_index,
            DAYS_PER_MONTH,
            p,
            nutzung_T,
            budget_T,
            demand_at_reference_price=demand_at_reference_price,
            reference_ecu_preis=reference_ecu_preis,
        )
    )
    bv = ecumenge_kontenrahmen_wert(p, budget_J)
    return p, nutzung_T, bv, ecumenge_T


def berechne_gesamtauslastung(nutzung_T: dict[str, float], budget_T: dict[str, float]) -> float:
    """Durchschnitt der Auslastung pro Grenze (NutzungT / BudgetT)."""
    parts = [
        nutzung_T[k] / budget_T[k] if budget_T[k] > 0 else 0.0
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

    budget_J = build_budget_J_bundle()
    budget_T = budget_T_from_budget_J(budget_J)
    base_epsilon = cfg.resolved_epsilon()
    frac = cfg.resolved_start_demand()
    demand_at_reference_price = {k: frac[k] * budget_T[k] for k in BOUNDARY_KEYS}
    annual = (
        demand_growth_per_year
        if demand_growth_per_year is not None
        else default_growth_by_key()
    )
    inv = float(steps_per_year)
    growth_per_period = {k: annual[k] ** (1.0 / inv) for k in BOUNDARY_KEYS}

    ecumenge_ziel = cfg.ecumenge_ziel
    ecumenge_J = ecumenge_J_from_start(frac, budget_J, ecumenge_ziel)
    ecumenge_budget_J = max(ecumenge_ziel, ecumenge_J)
    reference_ecu_preis = reference_ecu_preise_for_demand(cfg, budget_J, ecumenge_budget_J)

    timeline = ConsumptionTimeline(
        ecumenge_ziel=ecumenge_ziel,
        price_config=cfg.price,
        ecumenge_ziel_konfig=ecumenge_ziel,
        ecumenge_ziel_sim=max(ecumenge_ziel, ecumenge_J),
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
        p, nutzung_T, bv, ecu_cap_m = run_one_period(
            t + 1,
            timeline,
            budget_J,
            demand_at_reference_price,
            reference_ecu_preis,
            price_elasticity,
            ecumenge_ziel,
            ecumenge_J,
            cfg.consumption_budget_method,
            frac,
        )
        gesamtauslastung_val = berechne_gesamtauslastung(nutzung_T, budget_T)
        elastikfaktor_val = (
            dict(timeline.last_elastikfaktor)
            if timeline.last_elastikfaktor is not None
            else {k: 1.0 for k in BOUNDARY_KEYS}
        )
        xr = exchange_rates_for_ecu_preise(p)
        ecu_ist_T = ecumenge_kontenrahmen_wert(p, nutzung_T)
        w_sum = timeline.warmup_diag_sum_ecu_preis_budget_T_monthly
        w_ecu_m = timeline.warmup_diag_ecumenge_ziel_sim_monthly
        timeline.warmup_diag_sum_ecu_preis_budget_T_monthly = None
        timeline.warmup_diag_ecumenge_ziel_sim_monthly = None
        results.append(
            PeriodResult(
                period=t + 1,
                prices=p,
                nutzung_T=nutzung_T,
                budget_J=budget_J,
                budget_T=budget_T,
                ecumenge_kontenrahmen=bv,
                ecu_ist_T=ecu_ist_T,
                ecumenge_ziel=ecumenge_ziel,
                ecumenge_J=ecumenge_J,
                ecumenge_T=ecu_cap_m,
                gesamtauslastung=gesamtauslastung_val,
                elastikfaktor=elastikfaktor_val,
                ecu_per_unit=xr.ecu_per_unit,
                unit_per_ecu=xr.unit_per_ecu,
                demand_at_reference_price=dict(demand_at_reference_price),
                consumption_timeline=timeline,
                warmup_diag_sum_ecu_preis_budget_T_monthly=w_sum,
                warmup_diag_ecumenge_ziel_sim_monthly=w_ecu_m,
            )
        )
    return results
