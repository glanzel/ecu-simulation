"""
Konsum gegen eine **obere** ECU-Grenze E: Roh-Nachfrage bleibt unverändert, solange
``Σ_i p_i·c̃_i ≤ E``. Nur wenn die Nachfrage **mehr** ECU verbuchen würde als E,
wird der Konsum angepasst (nicht nach oben auf E aufgefüllt).

Zwei Varianten bei Überschreitung:

- **scale**: ``c_i = (E / Σ p·c̃) · c̃_i`` (einheitliche Drosselung).
- **lagrange**: Gewichte ``w_i = max(c̃_i, ε)``; Ausgaben wie Cobb-Douglas mit Budget ``E``:
  ``p_i c_i = E · w_i / Σ w_k``.
"""

from __future__ import annotations

from enum import Enum

from ecu_simulation.logic.observations import BOUNDARY_KEYS

_BUDGET_TOL = 1e-9


class ConsumptionBudgetMethod(str, Enum):
    """Wie Rohkonsum bei Überschreitung der ECU-Obergrenze gedrosselt wird."""

    SCALE = "scale"
    """Überschreitung: proportionale Skalierung auf ``Σ p·c = E``."""

    LAGRANGE = "lagrange"
    """Überschreitung: ``c_i = E · w_i / (p_i · Σ w_k)`` mit ``w_i = max(c̃_i, ε)``."""


_MIN_WEIGHT = 1e-30


def bundle_expenditure(
    prices: dict[str, float],
    consumption: dict[str, float],
) -> float:
    """``Σ_i p_i · consumption_i`` (verbuchte ECU im Abrechnungszeitraum, hier pro Monat)."""
    return sum(prices[k] * consumption[k] for k in BOUNDARY_KEYS)


def apply_consumption_budget(
    raw_consumption: dict[str, float],
    prices: dict[str, float],
    ecu_ceiling: float,
    method: ConsumptionBudgetMethod,
) -> dict[str, float]:
    """
    Wendet die ECU-**Obergrenze** ``ecu_ceiling`` an: kein Ausgeben mehr ECU als ``ecu_ceiling``;
    bei ungenutzter Kapazität bleibt der Rohkonsum unverändert (kein Hochskalieren auf ``E``).
    """
    if ecu_ceiling <= 0:
        raise ValueError("ecu_ceiling muss positiv sein.")
    spend = bundle_expenditure(prices, raw_consumption)
    if spend <= ecu_ceiling + _BUDGET_TOL:
        return {k: raw_consumption[k] for k in BOUNDARY_KEYS}
    if spend <= 0:
        raise ValueError(
            "Σ p·c̃ übersteigt die ECU-Obergrenze, ist aber nicht positiv — ungültige Rohdaten."
        )
    if method == ConsumptionBudgetMethod.SCALE:
        return _apply_scale_when_over(raw_consumption, prices, ecu_ceiling, spend)
    if method == ConsumptionBudgetMethod.LAGRANGE:
        return _apply_lagrange_weights(raw_consumption, prices, ecu_ceiling)
    raise ValueError(f"unbekannte ConsumptionBudgetMethod: {method!r}")


def _apply_scale_when_over(
    raw_consumption: dict[str, float],
    prices: dict[str, float],
    ecu_ceiling: float,
    spend: float,
) -> dict[str, float]:
    scale = ecu_ceiling / spend
    return {k: raw_consumption[k] * scale for k in BOUNDARY_KEYS}


def _apply_lagrange_weights(
    raw_consumption: dict[str, float],
    prices: dict[str, float],
    ecu_ceiling: float,
) -> dict[str, float]:
    weights = {k: max(raw_consumption[k], _MIN_WEIGHT) for k in BOUNDARY_KEYS}
    w_sum = sum(weights.values())
    out: dict[str, float] = {}
    for k in BOUNDARY_KEYS:
        pk = prices[k]
        if pk <= 0:
            raise ValueError(f"Schattenpreis für {k!r} muss positiv sein.")
        out[k] = ecu_ceiling * weights[k] / (pk * w_sum)
    return out
