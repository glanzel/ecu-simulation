"""
Zeitschritt-Simulation: Gleichgewichts-Schattenpreise, Tauschkurs, Konsum vs. VEJ.

Grenzenwerte als ``dict[str, float]`` (Schlüssel ``BOUNDARY_KEYS``); Beobachtungen als
``ConsumptionInterval`` / ``ConsumptionTimeline``.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable

from ecu_simulation.logic.exchange import rates_from_prices
from ecu_simulation.logic.observations import (
    BOUNDARY_KEYS,
    DAYS_PER_YEAR,
    ConsumptionInterval,
    ConsumptionTimeline,
)
from ecu_simulation.logic.planetary_constants import ALL_BOUNDARIES
from ecu_simulation.logic.prices import (
    bundle_value,
    consumption_all_below_vej,
    estimate_next_prices_from_timeline,
    enforce_ecu_floor,
    finalize_new_prices_on_last_interval,
    initial_weights_uniform,
    prices_from_weights,
    scale_to_ecu_budget,
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
    """Verbrauchsbeobachtungen dieser Periode (Gleichgewichtsschritte)."""


def build_vej_bundle() -> dict[str, float]:
    out: dict[str, float] = {}
    for b in ALL_BOUNDARIES:
        out[b.key] = compute_vej(b.AG, b.VK, b.RZ)
    return out


def _make_consumption_closure(
    demand_at_reference_price: dict[str, float],
    reference_shadow_price: dict[str, float],
    price_elasticity: dict[str, float],
):
    def consumption_at_prices(shadow: dict[str, float]) -> dict[str, float]:
        out: dict[str, float] = {}
        for k in BOUNDARY_KEYS:
            out[k] = consumption_quantity(
                shadow[k],
                demand_at_reference_price[k],
                reference_shadow_price[k],
                price_elasticity[k],
            )
        return out

    return consumption_at_prices


def run_equilibrium_prices(
    vej: dict[str, float],
    ecu_floor: float,
    cfg: SimulationConfig,
    realized_consumption: Callable[[dict[str, float]], dict[str, float]],
    zeitraum_days: float = DAYS_PER_YEAR,
) -> tuple[dict[str, float], dict[str, float], ConsumptionTimeline]:
    """
    Sucht (p, consumption) mit consumption_i ≤ VEJ_i und Σ p_i·VEJ_i ≥ ecu_floor.
    """
    timeline = ConsumptionTimeline()
    step = 0
    p = prices_from_weights(vej, ecu_floor, initial_weights_uniform(len(BOUNDARY_KEYS)))
    p = scale_to_ecu_budget(p, vej, ecu_floor)

    tol = cfg.tolerance
    consumption = realized_consumption(p)
    timeline.append(
        ConsumptionInterval.from_observation(step, zeitraum_days, p, consumption, vej),
    )
    step += 1

    if consumption_all_below_vej(consumption, vej, tol):
        p = enforce_ecu_floor(p, vej, ecu_floor, tol)
        finalize_new_prices_on_last_interval(timeline, p)
        consumption = realized_consumption(p)
        timeline.append(
            ConsumptionInterval.from_observation(step, zeitraum_days, p, consumption, vej),
        )
        return p, consumption, timeline

    for _ in range(cfg.max_price_iterations):
        p_next = estimate_next_prices_from_timeline(timeline, ecu_floor, cfg)
        last_prices = timeline.last.shadow_prices_map()
        unchanged = all(
            abs(p_next[k] - last_prices[k])
            <= tol * max(1.0, abs(last_prices[k]))
            for k in BOUNDARY_KEYS
        )
        consumption = realized_consumption(p_next)
        timeline.append(
            ConsumptionInterval.from_observation(step, zeitraum_days, p_next, consumption, vej),
        )
        step += 1

        if consumption_all_below_vej(consumption, vej, tol):
            p = enforce_ecu_floor(p_next, vej, ecu_floor, tol)
            finalize_new_prices_on_last_interval(timeline, p)
            consumption = realized_consumption(p)
            timeline.append(
                ConsumptionInterval.from_observation(step, zeitraum_days, p, consumption, vej),
            )
            return p, consumption, timeline

        if unchanged:
            break

    last_p = timeline.last.shadow_prices_map()
    p = enforce_ecu_floor(last_p, vej, ecu_floor, tol)
    finalize_new_prices_on_last_interval(timeline, p)
    consumption = realized_consumption(p)
    timeline.append(
        ConsumptionInterval.from_observation(step, zeitraum_days, p, consumption, vej),
    )
    return p, consumption, timeline


def run_period(
    vej: dict[str, float],
    demand_at_reference_price: dict[str, float],
    reference_shadow_price: dict[str, float],
    price_elasticity: dict[str, float],
    cfg: SimulationConfig,
    ecu_floor: float,
) -> tuple[dict[str, float], dict[str, float], float, ConsumptionTimeline]:
    realized_consumption = _make_consumption_closure(
        demand_at_reference_price, reference_shadow_price, price_elasticity
    )
    p, consumption, timeline = run_equilibrium_prices(
        vej, ecu_floor, cfg, realized_consumption, DAYS_PER_YEAR
    )
    bv = bundle_value(p, vej)
    return p, consumption, bv, timeline


def mean_boundary_utilization(consumption: dict[str, float], vej: dict[str, float]) -> float:
    """Durchschnitt der Auslastung pro Grenze (consumption/VEJ, maximal 1)."""
    parts = [
        min(1.0, consumption[k] / vej[k]) if vej[k] > 0 else 0.0
        for k in BOUNDARY_KEYS
    ]
    return sum(parts) / len(parts)


def next_ecu_budget(current: float, mean_u: float, cfg: SimulationConfig) -> float:
    """Steigt mittlere Auslastung → EcuJ senken; fällt sie → erhöhen."""
    factor = 1.0 - cfg.ecu_adjustment_kappa * (mean_u - cfg.utilization_target)
    nxt = current * factor
    return max(cfg.ecu_min, min(cfg.ecu_max, nxt))


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
    p_start = prices_from_weights(vej, ecu_current, initial_weights_uniform(len(BOUNDARY_KEYS)))
    p_start = scale_to_ecu_budget(p_start, vej, ecu_current)
    reference_shadow_price = cfg.resolved_p_ref(p_start)

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
        p, consumption, bv, consumption_timeline = run_period(
            vej,
            demand_at_reference_price,
            reference_shadow_price,
            price_elasticity,
            cfg,
            ecu_floor,
        )
        mean_u = mean_boundary_utilization(consumption, vej)
        xr = rates_from_prices(p)
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
                consumption_timeline=consumption_timeline,
            )
        )
        ecu_current = next_ecu_budget(ecu_current, mean_u, cfg)
    return results
