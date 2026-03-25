"""
Schattenpreise (ECU pro Einheit Kontrollvariable) mit Kopplung an EcuJ:

  EcuJ ≤ Σ_i p_i · VEJ_i

Werte pro Grenze: ``dict[str, float]`` mit Schlüsseln aus ``BOUNDARY_KEYS``.
"""

from __future__ import annotations

import math
from typing import Sequence

from ecu_simulation.config import BOUNDARY_KEYS, SimulationConfig
from ecu_simulation.observations import ConsumptionTimeline


def initial_weights_uniform(n: int) -> list[float]:
    """Gleichverteilung der Gewichte (für Start-Schattenpreise)."""
    return [1.0 / n] * n


def prices_from_weights(
    vej: dict[str, float],
    ecu_per_year: float,
    weights: Sequence[float],
) -> dict[str, float]:
    """
    Initialer Schattenpreisvektor aus Gewichten:

        ``p_i = w_i * ecu_per_year / VEJ_i`` mit ``Σ w_i = 1``.
    """
    keys = list(BOUNDARY_KEYS)
    if len(weights) != len(keys):
        raise ValueError("weights passt nicht zu Grenzen.")
    s = sum(weights)
    if s <= 0:
        raise ValueError("Gewichte müssen positiv summieren.")
    w = [wi / s for wi in weights]
    out: dict[str, float] = {}
    for i, k in enumerate(keys):
        v = vej[k]
        if v <= 0:
            raise ValueError(f"VEJ für {k} muss positiv sein.")
        out[k] = w[i] * ecu_per_year / v
    return out


def bundle_value(prices: dict[str, float], vej: dict[str, float]) -> float:
    """``Σ_i p_i * VEJ_i``."""
    return sum(prices[k] * vej[k] for k in BOUNDARY_KEYS)


def scale_to_ecu_budget(
    prices: dict[str, float],
    vej: dict[str, float],
    ecu_per_year: float,
) -> dict[str, float]:
    """Skaliert alle ``p`` multiplikativ, sodass ``Σ p_i·VEJ_i = ecu_per_year``."""
    total = bundle_value(prices, vej)
    if total <= 0:
        raise ValueError("Summe p·VEJ muss positiv sein.")
    s = ecu_per_year / total
    return {k: prices[k] * s for k in BOUNDARY_KEYS}


def enforce_ecu_floor(
    prices: dict[str, float],
    vej: dict[str, float],
    ecu_floor: float,
    tol: float = 1e-12,
) -> dict[str, float]:
    """
    Stellt die EcuJ-Untergrenze sicher (Slack erlaubt, wenn Summe schon ≥ ecu_floor).
    """
    total = bundle_value(prices, vej)
    if total <= 0:
        raise ValueError("Summe p·VEJ muss positiv sein.")
    if total + tol < ecu_floor:
        return scale_to_ecu_budget(prices, vej, ecu_floor)
    return {k: prices[k] for k in BOUNDARY_KEYS}


def consumption_all_below_vej(
    consumption: dict[str, float],
    vej: dict[str, float],
    tol: float,
) -> bool:
    """True, wenn ``consumption_i ≤ vej_i + tol`` für alle Grenzen."""
    return all(consumption[k] <= vej[k] + tol for k in BOUNDARY_KEYS)


def _implied_elasticity_from_history(
    p_prev: float,
    p_last: float,
    consumption_prev: float,
    consumption_last: float,
    eta_clip: tuple[float, float],
) -> float | None:
    """Lokale numerische Elastizität ``d ln(consumption) / d ln(p)``."""
    if (
        p_prev <= 0
        or p_last <= 0
        or consumption_prev <= 0
        or consumption_last <= 0
    ):
        return None
    lp = math.log(p_last / p_prev)
    if abs(lp) < 1e-14:
        return None
    lu = math.log(consumption_last / consumption_prev)
    eta = lu / lp
    if eta >= 0:
        return None
    lo, hi = eta_clip
    if eta < lo:
        eta = lo
    elif eta > hi:
        eta = hi
    return eta


def estimate_next_prices_from_timeline(
    timeline: ConsumptionTimeline,
    ecu_floor: float,
    cfg: SimulationConfig,
) -> dict[str, float]:
    """
    Nächster Preisvektor aus der Timeline; schreibt ``new_price`` ins letzte Intervall.

    VEJ und Preise stammen aus den ``ConsumptionRecord`` des letzten Intervalls.
    """
    if len(timeline) == 0:
        raise ValueError("timeline muss mindestens ein ConsumptionInterval enthalten.")

    last_interval = timeline.last
    tol = cfg.tolerance
    bump = cfg.price_bump

    vej_last = {k: last_interval.vej_for(k) for k in BOUNDARY_KEYS}
    p_last = {k: last_interval.price_for(k) for k in BOUNDARY_KEYS}
    consumption_last = {k: last_interval.consumption_for(k) for k in BOUNDARY_KEYS}

    if consumption_all_below_vej(consumption_last, vej_last, tol):
        p_final = enforce_ecu_floor(p_last, vej_last, ecu_floor, tol)
    else:
        p_new = {k: p_last[k] for k in BOUNDARY_KEYS}
        has_prev = len(timeline) >= 2
        prev_interval = timeline[-2] if has_prev else None

        for k in BOUNDARY_KEYS:
            if consumption_last[k] <= vej_last[k] + tol:
                continue

            mult = bump
            if has_prev and prev_interval is not None:
                p_prev = prev_interval.price_for(k)
                consumption_prev = prev_interval.consumption_for(k)

                eta = _implied_elasticity_from_history(
                    p_prev,
                    p_last[k],
                    consumption_prev,
                    consumption_last[k],
                    cfg.price_eta_clip,
                )
                if eta is not None:
                    ratio_target = vej_last[k] / consumption_last[k]
                    if 0.0 < ratio_target < 1.0:
                        raw = math.exp(math.log(ratio_target) / eta)
                        lo, hi = cfg.price_step_multiplier_clip
                        mult = max(lo, min(hi, raw))
            p_new[k] = p_new[k] * mult

        p_final = enforce_ecu_floor(p_new, vej_last, ecu_floor, tol)

    timeline.apply_new_prices_to_last(p_final)
    return p_final


def finalize_new_prices_on_last_interval(
    timeline: ConsumptionTimeline,
    prices_after_enforce: dict[str, float],
) -> None:
    """Setzt ``new_price`` auf dem letzten Intervall."""
    timeline.apply_new_prices_to_last(prices_after_enforce)
