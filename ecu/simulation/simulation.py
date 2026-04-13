"""
Zeitschritt-Simulation: pro Periode zuerst Schattenpreise (``advance_shadow_prices``),
dann genau ein Konsum; eine gemeinsame ``ConsumptionTimeline`` über alle Perioden.

Schattenpreise und ECU-Logik liegen in ``logic.prices``.
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
from ecu.logic.planetary_constants import ALL_BOUNDARIES
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
    consumption: dict[str, float]
    vej: dict[str, float]
    """Jährliche VEJ (Referenz; VET = VEJ/12)."""
    vet: dict[str, float]
    """Monatliche Obergrenze pro Grenze (Konsumintervall)."""
    bundle_ecu: float
    """Σ p·VEJ — Wert des vollen VEJ-Bündels zu den Schattenpreisen (Preis-/Kontenrahmen, jährlich)."""
    ecu_expenditure: float
    """Σ p·consumption — tatsächlich verbuchte ECU im Monat (Summe der Grenz-Spalte p·c)."""
    ecu_per_year: float
    """Verteiltes ECU-Jahresvolumen (EcuJ), wie ``SimulationConfig.ecu_per_year``; in der Preislogik Ziel Σ p·VEJ."""
    mean_utilization: float
    """Mittel aus consumption/VET über die drei Grenzen (kann > 1 sein, z. B. Grenzüberschreitung)."""
    ecu_per_unit: dict[str, float]
    unit_per_ecu: dict[str, float]
    demand_at_reference_price: dict[str, float]
    consumption_timeline: ConsumptionTimeline
    """Gemeinsame, fortlaufende Timeline (bis einschließlich dieser Periode)."""


def build_vej_bundle() -> dict[str, float]:
    out: dict[str, float] = {}
    for b in ALL_BOUNDARIES:
        out[b.key] = compute_vej(b.AG, b.VK, b.RZ)
    return out


def vet_from_vej(vej: dict[str, float]) -> dict[str, float]:
    """Monatliche Obergrenze VET = VEJ / 12 (glattes Jahr)."""
    inv = float(MONTHS_PER_YEAR)
    return {k: vej[k] / inv for k in BOUNDARY_KEYS}


def _raw_consumption_at_prices(
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
    vej: dict[str, float],
    demand_at_reference_price: dict[str, float],
    reference_shadow_price: dict[str, float],
    price_elasticity: dict[str, float],
    ecu_per_year: float,
    budget_method: ConsumptionBudgetMethod,
    fraction_of_vej: dict[str, float],
) -> tuple[dict[str, float], dict[str, float], float]:
    """
    Ein Monat: zuerst ``advance_shadow_prices`` (Preise für diesen Konsum),
    dann Roh-Nachfrage, ggf. Drosselung auf ``Σ p·c ≤ ecu_per_year/12`` via ``budget_method``,
    dann ein neues Intervall an der gemeinsamen Timeline.
    """
    timeline.ecu_per_year = ecu_per_year
    advance_shadow_prices(timeline, vej, fraction_of_vej)
    p = timeline.prices_for_next_consumption
    if p is None:
        raise RuntimeError(
            "advance_shadow_prices muss prices_for_next_consumption setzen."
        )
    raw = _raw_consumption_at_prices(
        p, demand_at_reference_price, reference_shadow_price, price_elasticity
    )
    ecu_ceiling_month = ecu_per_year / float(MONTHS_PER_YEAR)
    c = apply_consumption_budget(raw, p, ecu_ceiling_month, budget_method)
    vet = vet_from_vej(vej)
    timeline.append(
        ConsumptionInterval.from_observation(
            period_index,
            DAYS_PER_MONTH,
            p,
            c,
            vet,
            demand_at_reference_price=demand_at_reference_price,
            reference_shadow_price=reference_shadow_price,
        )
    )
    bv = bundle_value(p, vej)
    return p, c, bv


def mean_boundary_utilization(consumption: dict[str, float], vet: dict[str, float]) -> float:
    """Durchschnitt der Auslastung pro Grenze (consumption/VET)."""
    parts = [
        consumption[k] / vet[k] if vet[k] > 0 else 0.0
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
    Konsum: ``cfg.consumption_budget_method`` begrenzt ``Σ p·consumption ≤ ecu_per_year/12`` pro Monat.
    """
    if cfg.random_seed is not None:
        random.seed(cfg.random_seed)

    if steps_per_year < 1:
        raise ValueError("steps_per_year muss mindestens 1 sein.")

    vej = build_vej_bundle()
    vet = vet_from_vej(vej)
    base_epsilon = cfg.resolved_epsilon()
    frac = cfg.resolved_d0_fraction()
    demand_at_reference_price = {k: frac[k] * vet[k] for k in BOUNDARY_KEYS}
    annual = demand_growth_per_year or {k: 1.0 for k in BOUNDARY_KEYS}
    inv = float(steps_per_year)
    growth_per_period = {k: annual[k] ** (1.0 / inv) for k in BOUNDARY_KEYS}

    ecu_per_year = cfg.ecu_per_year
    reference_shadow_price = reference_shadow_prices_for_demand(cfg, vej, ecu_per_year)

    timeline = ConsumptionTimeline(ecu_per_year=ecu_per_year, price_config=cfg.price)
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
        p, consumption, bv = run_one_period(
            t + 1,
            timeline,
            vej,
            demand_at_reference_price,
            reference_shadow_price,
            price_elasticity,
            ecu_per_year,
            cfg.consumption_budget_method,
            frac,
        )
        mean_u = mean_boundary_utilization(consumption, vet)
        xr = exchange_rates_for_shadow_prices(p)
        ecu_expenditure = bundle_value(p, consumption)
        results.append(
            PeriodResult(
                period=t + 1,
                prices=p,
                consumption=consumption,
                vej=vej,
                vet=vet,
                bundle_ecu=bv,
                ecu_expenditure=ecu_expenditure,
                ecu_per_year=ecu_per_year,
                mean_utilization=mean_u,
                ecu_per_unit=xr.ecu_per_unit,
                unit_per_ecu=xr.unit_per_ecu,
                demand_at_reference_price=dict(demand_at_reference_price),
                consumption_timeline=timeline,
            )
        )
    return results
