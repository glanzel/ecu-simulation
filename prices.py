"""
Schattenpreise p_i (ECU pro Einheit Kontrollvariable) mit Kopplung an EcuJ:

  EcuJ ≤ Σ_i p_i · VEJ_i   (Untergrenze für den „Wert“ der vollen VEJ-Bündel in ECU)

Es wird **nicht** auf Gleichheit normiert: Ist die Summe bereits ≥ EcuJ, bleibt Slack;
liegt sie darunter, werden die Preise **hoch**skaliert, bis die Summe die Untergrenze erreicht.

Preisfindung (in ``estimate_next_prices_from_timeline``): ausschließlich aus der
``ConsumptionTimeline``. Dieses Modul kennt **keine** Nachfragefunktion und importiert
das Paket ``demand`` nicht — die Simulation liefert beobachtete Konsumdaten.
"""

from __future__ import annotations

import math
from typing import Sequence

from ecu_simulation.config import BOUNDARY_KEYS, SimulationConfig
from ecu_simulation.observations import ConsumptionTimeline, apply_new_prices_to_last_interval


def initial_weights_uniform(n: int) -> list[float]:
    return [1.0 / n] * n


def prices_from_weights(
    vej: dict[str, float],
    ecu_per_year: float,
    weights: Sequence[float],
) -> dict[str, float]:
    """p_i = w_i * ecu_per_year / VEJ_i mit Σ w_i = 1."""
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
    """Σ p_i · VEJ_i."""
    return sum(prices[k] * vej[k] for k in BOUNDARY_KEYS)


def scale_to_ecu_budget(
    prices: dict[str, float],
    vej: dict[str, float],
    ecu_per_year: float,
) -> dict[str, float]:
    """Skaliert alle p multiplikativ, sodass Σ p_i·VEJ_i = ecu_per_year (Startwert / Mindest-Skalierung)."""
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
    Stellt EcuJ ≤ Σ p_i·VEJ_i sicher: nur wenn die Summe unter ecu_floor liegt, hochskalieren.
    Liegt die Summe bereits darüber, bleibt der Preisvektor unverändert (Ungleichung mit Slack).
    """
    total = bundle_value(prices, vej)
    if total <= 0:
        raise ValueError("Summe p·VEJ muss positiv sein.")
    if total + tol < ecu_floor:
        return scale_to_ecu_budget(prices, vej, ecu_floor)
    return {k: prices[k] for k in BOUNDARY_KEYS}


def _implied_elasticity_from_history(
    p_prev: float,
    p_last: float,
    u_prev: float,
    u_last: float,
    eta_clip: tuple[float, float],
) -> float | None:
    """
    Lokale Elastizität η̂ = d ln u / d ln p aus zwei aufeinanderfolgenden Beobachtungen.
    Nur sinnvoll, wenn η̂ < 0 (fallende Nachfrage bei höherem Preis).
    """
    if p_prev <= 0 or p_last <= 0 or u_prev <= 0 or u_last <= 0:
        return None
    lp = math.log(p_last / p_prev)
    if abs(lp) < 1e-14:
        return None
    lu = math.log(u_last / u_prev)
    eta = lu / lp
    if eta >= 0:
        return None
    lo, hi = eta_clip
    if eta < lo:
        eta = lo
    elif eta > hi:
        eta = hi
    return eta


def _timeline_to_price_demand_pairs(
    timeline: ConsumptionTimeline,
) -> list[tuple[dict[str, float], dict[str, float]]]:
    """Liest aus der Timeline die beobachteten (price, value)-Paare je Schritt."""
    out: list[tuple[dict[str, float], dict[str, float]]] = []
    for interval in timeline:
        p = {r.control_variable_key: r.price for r in interval.records}
        u = {r.control_variable_key: r.value for r in interval.records}
        out.append((p, u))
    return out


def _estimate_next_prices_from_pairs(
    history: list[tuple[dict[str, float], dict[str, float]]],
    vej: dict[str, float],
    ecu_floor: float,
    cfg: SimulationConfig,
) -> dict[str, float]:
    """Kernregel aus der Historie von (p, u)-Paaren (intern)."""
    if not history:
        raise ValueError("history muss mindestens eine (p, u)-Beobachtung enthalten.")
    p_last = {k: history[-1][0][k] for k in BOUNDARY_KEYS}
    u_last = {k: history[-1][1][k] for k in BOUNDARY_KEYS}
    tol = cfg.tolerance
    bump = cfg.price_bump

    if all(u_last[k] <= vej[k] + tol for k in BOUNDARY_KEYS):
        return enforce_ecu_floor(p_last, vej, ecu_floor, tol)

    p_new = {k: p_last[k] for k in BOUNDARY_KEYS}
    has_prev = len(history) >= 2
    p_prev = {k: history[-2][0][k] for k in BOUNDARY_KEYS} if has_prev else None
    u_prev = {k: history[-2][1][k] for k in BOUNDARY_KEYS} if has_prev else None

    for k in BOUNDARY_KEYS:
        if u_last[k] <= vej[k] + tol:
            continue
        mult = bump
        if has_prev and p_prev is not None and u_prev is not None:
            eta = _implied_elasticity_from_history(
                p_prev[k], p_last[k], u_prev[k], u_last[k], cfg.price_eta_clip
            )
            if eta is not None:
                ratio_target = vej[k] / u_last[k]
                if ratio_target > 0 and ratio_target < 1.0:
                    raw = math.exp(math.log(ratio_target) / eta)
                    lo, hi = cfg.price_step_multiplier_clip
                    mult = max(lo, min(hi, raw))
        p_new[k] *= mult

    return enforce_ecu_floor(p_new, vej, ecu_floor, tol)


def estimate_next_prices_from_timeline(
    timeline: ConsumptionTimeline,
    vej: dict[str, float],
    ecu_floor: float,
    cfg: SimulationConfig,
) -> dict[str, float]:
    """
    Nächster Preisvektor aus der ``ConsumptionTimeline``; schreibt **nur**
    ``ConsumptionRecord.new_price`` auf dem **letzten** Intervall (nach EcuJ-Boden).
    """
    if not timeline:
        raise ValueError("timeline muss mindestens ein ConsumptionInterval enthalten.")
    pairs = _timeline_to_price_demand_pairs(timeline)
    p_final = _estimate_next_prices_from_pairs(pairs, vej, ecu_floor, cfg)
    apply_new_prices_to_last_interval(timeline, p_final)
    return p_final


def finalize_new_prices_on_last_interval(
    timeline: ConsumptionTimeline,
    prices_after_enforce: dict[str, float],
) -> None:
    """
    Setzt ``new_price`` auf dem letzten Intervall (z. B. nach erstem ``enforce_ecu_floor``).
    Sollte nur dort aufgerufen werden, wo die Preislogik den Vorschlag bestätigt.
    """
    apply_new_prices_to_last_interval(timeline, prices_after_enforce)
