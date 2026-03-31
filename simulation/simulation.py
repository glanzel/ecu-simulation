"""
Zeitschritt-Simulation: pro Periode zuerst Schattenpreise (``advance_shadow_prices``),
dann genau ein Konsum; eine gemeinsame ``ConsumptionTimeline`` über alle Perioden.

Schattenpreise und ECU-Logik liegen in ``logic.prices``.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from ecu_simulation.logic.observations import (
    BOUNDARY_KEYS,
    DAYS_PER_YEAR,
    ConsumptionInterval,
    ConsumptionTimeline,
)
from ecu_simulation.logic.planetary_constants import ALL_BOUNDARIES
from ecu_simulation.logic.prices import (
    advance_shadow_prices,
    bundle_value,
    exchange_rates_for_shadow_prices,
    next_ecu_budget,
    reference_shadow_prices_for_demand,
)
from ecu_simulation.logic.vej import compute_vej
from ecu_simulation.simulation.config import SimulationConfig
from ecu_simulation.simulation.demand import consumption_quantity


@dataclass
class PeriodResult:
    period: int
    prices: dict[str, float]
    consumption: dict[str, float]
    vej: dict[str, float]
    bundle_ecu: float
    """Σ p·VEJ — erfüllt EcuJ ≤ bundle_ecu (Slack möglich)."""
    ecu_floor: float
    """Untergrenze EcuJ dieser Periode (verteiltes ECU-Volumen)."""
    mean_utilization: float
    """Mittel aus min(consumption/VEJ, 1) über die drei Grenzen."""
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


def _consumption_at_prices(
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
    ecu_floor: float,
) -> tuple[dict[str, float], dict[str, float], float]:
    """
    Eine Periode: zuerst ``advance_shadow_prices`` (Preise für diesen Konsum),
    dann genau ein Konsum und genau ein neues Intervall an der gemeinsamen Timeline.
    """
    timeline.ecu_floor = ecu_floor
    advance_shadow_prices(timeline, vej)
    p = timeline.prices_for_next_consumption
    if p is None:
        raise RuntimeError(
            "advance_shadow_prices muss prices_for_next_consumption setzen."
        )
    c = _consumption_at_prices(
        p, demand_at_reference_price, reference_shadow_price, price_elasticity
    )
    timeline.append(
        ConsumptionInterval.from_observation(
            period_index,
            DAYS_PER_YEAR,
            p,
            c,
            vej,
            demand_at_reference_price=demand_at_reference_price,
            reference_shadow_price=reference_shadow_price,
        )
    )
    bv = bundle_value(p, vej)
    return p, c, bv


def mean_boundary_utilization(consumption: dict[str, float], vej: dict[str, float]) -> float:
    """Durchschnitt der Auslastung pro Grenze (consumption/VEJ, maximal 1)."""
    parts = [
        min(1.0, consumption[k] / vej[k]) if vej[k] > 0 else 0.0
        for k in BOUNDARY_KEYS
    ]
    return sum(parts) / len(parts)


def run_simulation(
    cfg: SimulationConfig,
    periods: int,
    demand_growth_per_period: dict[str, float] | None = None,
) -> list[PeriodResult]:
    """
    periods: Anzahl Zeitschritte.
    demand_growth_per_period: multiplikativer Faktor pro Grenze pro Periode (z. B. nur co2 > 1).
    """
    if cfg.random_seed is not None:
        random.seed(cfg.random_seed)

    vej = build_vej_bundle()
    price_elasticity = cfg.resolved_epsilon()
    frac = cfg.resolved_d0_fraction()
    demand_at_reference_price = {k: frac[k] * vej[k] for k in BOUNDARY_KEYS}
    growth = demand_growth_per_period or {k: 1.0 for k in BOUNDARY_KEYS}

    ecu_current = cfg.ecu_per_year
    reference_shadow_price = reference_shadow_prices_for_demand(cfg, vej, ecu_current)

    timeline = ConsumptionTimeline(ecu_floor=ecu_current, price_config=cfg.price)
    results: list[PeriodResult] = []
    noise_std = cfg.demand_at_reference_price_log_noise_std
    for t in range(periods):
        demand_at_reference_price = {
            k: demand_at_reference_price[k] * growth[k] for k in BOUNDARY_KEYS
        }
        if noise_std > 0.0:
            for k in BOUNDARY_KEYS:
                demand_at_reference_price[k] *= math.exp(random.gauss(0.0, noise_std))
        ecu_floor = ecu_current
        p, consumption, bv = run_one_period(
            t + 1,
            timeline,
            vej,
            demand_at_reference_price,
            reference_shadow_price,
            price_elasticity,
            ecu_floor,
        )
        mean_u = mean_boundary_utilization(consumption, vej)
        xr = exchange_rates_for_shadow_prices(p)
        results.append(
            PeriodResult(
                period=t + 1,
                prices=p,
                consumption=consumption,
                vej=vej,
                bundle_ecu=bv,
                ecu_floor=ecu_floor,
                mean_utilization=mean_u,
                ecu_per_unit=xr.ecu_per_unit,
                unit_per_ecu=xr.unit_per_ecu,
                demand_at_reference_price=dict(demand_at_reference_price),
                consumption_timeline=timeline,
            )
        )
        ecu_current = next_ecu_budget(ecu_current, mean_u, cfg)
    return results
