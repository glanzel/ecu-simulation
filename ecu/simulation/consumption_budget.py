"""
Konsum gegen eine **obere** ECU-Grenze E: Roh-Nachfrage bleibt unverändert, solange
``Σ_i p_i·c̃_i ≤ E``. Nur wenn die Nachfrage **mehr** ECU verbuchen würde als E,
wird der Konsum angepasst (nicht nach oben auf E aufgefüllt).

Zwei Varianten bei Überschreitung:

- **scale**: ``c_i = (E / Σ p·c̃) · c̃_i`` (einheitliche Drosselung).
- **lagrange**: EUKLIDISCH nächstliegender zulässiger Konsum zu ``c̃`` unter ``Σ p·c = E``, ``c ≥ 0``:
  ``c_i = max(0, c̃_i − λ p_i)`` mit ``λ`` aus Bisektion auf ``Σ p·c = E``.
"""

from __future__ import annotations

from enum import Enum

from ecu.logic.observations import BOUNDARY_KEYS

_BUDGET_TOL = 1e-9


class ConsumptionBudgetMethod(str, Enum):
    """Wie Rohkonsum bei Überschreitung der ECU-Obergrenze gedrosselt wird."""

    SCALE = "scale"
    """Überschreitung: proportionale Skalierung auf ``Σ p·c = E``."""

    LAGRANGE = "lagrange"
    """Überschreitung: ``c`` minimiert ``Σ (c_i − c̃_i)²`` bei ``Σ p·c = E``, ``c ≥ 0`` (Projektion)."""


def bundle_expenditure(
    prices: dict[str, float],
    vej_ist: dict[str, float],
) -> float:
    """``Σ_i p_i · vej_ist_i`` (verbuchte ECU im Abrechnungszeitraum, hier pro Monat)."""
    return sum(prices[k] * vej_ist[k] for k in BOUNDARY_KEYS)


def apply_consumption_budget(
    raw_vej_ist: dict[str, float],
    prices: dict[str, float],
    ecumenge_T: float,
    method: ConsumptionBudgetMethod,
) -> dict[str, float]:
    """
    Wendet die simulierte ECU-Menge ``ecumenge_T`` (Obergrenze) an: nicht mehr ausgeben als ``ecumenge_T``;
    bei ungenutzter Kapazität bleibt der Rohkonsum unverändert (kein Hochskalieren auf ``E``).
    """
    if ecumenge_T <= 0:
        raise ValueError("ecumenge_T muss positiv sein.")
    spend = bundle_expenditure(prices, raw_vej_ist)
    if spend <= ecumenge_T + _BUDGET_TOL:
        return {k: raw_vej_ist[k] for k in BOUNDARY_KEYS}
    if spend <= 0:
        raise ValueError(
            "Σ p·c̃ übersteigt die ECU-Obergrenze, ist aber nicht positiv — ungültige Rohdaten."
        )
    if method == ConsumptionBudgetMethod.SCALE:
        return _apply_scale_when_over(raw_vej_ist, prices, ecumenge_T, spend)
    if method == ConsumptionBudgetMethod.LAGRANGE:
        return _apply_lagrange_project_demands(raw_vej_ist, prices, ecumenge_T)
    raise ValueError(f"unbekannte ConsumptionBudgetMethod: {method!r}")


def _apply_scale_when_over(
    raw_vej_ist: dict[str, float],
    prices: dict[str, float],
    ecumenge_T: float,
    spend: float,
) -> dict[str, float]:
    scale = ecumenge_T / spend
    return {k: raw_vej_ist[k] * scale for k in BOUNDARY_KEYS}


def _expenditure_at_lambda(
    raw_vej_ist: dict[str, float],
    prices: dict[str, float],
    lam: float,
) -> float:
    """``Σ_k p_k · max(0, c̃_k − λ p_k)`` — fällt monoton in ``λ``."""
    out = 0.0
    for k in BOUNDARY_KEYS:
        pk = prices[k]
        if pk <= 0:
            raise ValueError(f"Schattenpreis für {k!r} muss positiv sein.")
        out += pk * max(0.0, raw_vej_ist[k] - lam * pk)
    return out


def _apply_lagrange_project_demands(
    raw_vej_ist: dict[str, float],
    prices: dict[str, float],
    ecumenge_T: float,
) -> dict[str, float]:
    """Minimiert ``Σ (c_k − c̃_k)²`` bei ``Σ p·c = E``, ``c_k ≥ 0`` → ``c_k = max(0, c̃_k − λ p_k)``."""
    hi = 1.0
    while _expenditure_at_lambda(raw_vej_ist, prices, hi) > ecumenge_T + _BUDGET_TOL:
        hi *= 2.0
        if hi > 1e100:
            raise ValueError("Lagrange-Projektion: keine gültige λ-Obergrenze.")
    lo = 0.0
    for _ in range(90):
        mid = 0.5 * (lo + hi)
        if _expenditure_at_lambda(raw_vej_ist, prices, mid) > ecumenge_T:
            lo = mid
        else:
            hi = mid
    lam = 0.5 * (lo + hi)
    return {k: max(0.0, raw_vej_ist[k] - lam * prices[k]) for k in BOUNDARY_KEYS}
