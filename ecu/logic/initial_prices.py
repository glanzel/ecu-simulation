"""
Start-Schattenpreise aus relativen Gewichten und VEJ (Bootstrap, erstes Jahr).

Die eigentliche ECU-Normierung und Folgeperioden liegen in ``logic.prices``.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from ecu.logic.observations import BOUNDARY_KEYS

_MIN_UTILIZATION: float = 1e-9


def initial_weights_uniform(n: int) -> list[float]:
    """
    Erzeugt ``n`` gleich große Gewichte (Summe 1), z. B. für Start-Schattenpreise.

    Jedes Gewicht ist ``1/n``.
    """
    return [1.0 / n] * n


def prices_from_weights(
    vej_ziel: dict[str, float],
    ecu_per_year: float,
    weights: Sequence[float],
) -> dict[str, float]:
    """
    Baut den Start-Schattenpreis je Grenze aus relativen Gewichten und Jahres-ECU-Budget.

    Formel pro Grenze *i*: ``p_i = w_i · ecu_per_year / VEJ-Ziel_i``, wobei die Eingabe-
    gewichte zuerst auf Summe 1 normiert werden (``Σ w_i = 1``).

    ``ecu_per_year`` ist das Ziel für die gewichtete Summe ``Σ_i p_i · VEJ-Ziel_i`` nach
    Normierung der Gewichte (vor weiterer Skalierung durch andere Schritte).
    """
    boundary_order = list(BOUNDARY_KEYS)
    if len(weights) != len(boundary_order):
        raise ValueError("weights passt nicht zu Grenzen.")
    weight_sum = sum(weights)
    if weight_sum <= 0:
        raise ValueError("Gewichte müssen positiv summieren.")
    normalized_weights = [wi / weight_sum for wi in weights]
    shadow_prices: dict[str, float] = {}
    for index, boundary_key in enumerate(boundary_order):
        vej_ziel_at = vej_ziel[boundary_key]
        if vej_ziel_at <= 0:
            raise ValueError(f"VEJ-Ziel für {boundary_key} muss positiv sein.")
        shadow_prices[boundary_key] = (
            normalized_weights[index] * ecu_per_year / vej_ziel_at
        )
    return shadow_prices


def raw_initial_shadow_prices_from_utilization(
    vej_ziel: dict[str, float],
    ecu_per_year_soll: float,
    utilization_by_boundary: Mapping[str, float],
    weights: Sequence[float],
) -> dict[str, float]:
    """
    Roh-Startpreise: ``p_i = w_i · (E_soll · u_avg) / (VEJ-Ziel_i · max(u_i, ε))`` mit normierten
    Gewichten ``w_i`` (Summe 1) und ``u_avg`` = Mittel der ``u_i`` je Grenze.
    """
    boundary_order = list(BOUNDARY_KEYS)
    if len(weights) != len(boundary_order):
        raise ValueError("weights passt nicht zu Grenzen.")
    weight_sum = sum(weights)
    if weight_sum <= 0:
        raise ValueError("Gewichte müssen positiv summieren.")
    normalized_weights = [wi / weight_sum for wi in weights]
    u_safe = [max(_MIN_UTILIZATION, float(utilization_by_boundary[k])) for k in boundary_order]
    u_avg = sum(u_safe) / float(len(u_safe))
    if ecu_per_year_soll <= 0:
        raise ValueError("ecu_per_year_soll muss positiv sein.")
    out: dict[str, float] = {}
    for index, boundary_key in enumerate(boundary_order):
        vej_ziel_at = vej_ziel[boundary_key]
        if vej_ziel_at <= 0:
            raise ValueError(f"VEJ-Ziel für {boundary_key} muss positiv sein.")
        out[boundary_key] = (
            normalized_weights[index] * ecu_per_year_soll * u_avg / (vej_ziel_at * u_safe[index])
        )
    return out
