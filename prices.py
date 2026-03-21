"""
Schattenpreise p_i (ECU pro Einheit Kontrollvariable) mit Kopplung an EcuJ:

  EcuJ ≤ Σ_i p_i · VEJ_i   (Untergrenze für den „Wert“ der vollen VEJ-Bündel in ECU)

Es wird **nicht** auf Gleichheit normiert: Ist die Summe bereits ≥ EcuJ, bleibt Slack;
liegt sie darunter, werden die Preise **hoch**skaliert, bis die Summe die Untergrenze erreicht.

Kybernetik: bei zu hoher Nachfrage werden einzelne p_i erhöht (Preisdruck).
"""

from __future__ import annotations

from typing import Callable, Sequence

from ecu_sim.config import BOUNDARY_KEYS, SimulationConfig


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


def equilibrium_prices(
    vej: dict[str, float],
    ecu_floor: float,
    demand_at: Callable[[dict[str, float]], dict[str, float]],
    cfg: SimulationConfig,
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Findet (p, u) sodass u_i ≤ VEJ_i und Σ p_i·VEJ_i ≥ ecu_floor (Untergrenze EcuJ).

    Iteration: bei u_i > VEJ_i wird p_i erhöht; anschließend nur Hochskalierung, falls Summe < ecu_floor.
    """
    p = prices_from_weights(vej, ecu_floor, initial_weights_uniform(len(BOUNDARY_KEYS)))
    p = scale_to_ecu_budget(p, vej, ecu_floor)

    bump = cfg.price_bump
    tol = cfg.tolerance
    for _ in range(cfg.max_price_iterations):
        u = demand_at(p)
        if all(u[k] <= vej[k] + tol for k in BOUNDARY_KEYS):
            p = enforce_ecu_floor(p, vej, ecu_floor, tol)
            u = demand_at(p)
            return p, u
        changed = False
        for k in BOUNDARY_KEYS:
            if u[k] > vej[k] + tol:
                p[k] *= bump
                changed = True
        if not changed:
            break
        p = enforce_ecu_floor(p, vej, ecu_floor, tol)

    p = enforce_ecu_floor(p, vej, ecu_floor, tol)
    u = demand_at(p)
    return p, u
