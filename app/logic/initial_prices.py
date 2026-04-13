"""
Start-Schattenpreise aus relativen Gewichten und VEJ (Bootstrap, erstes Jahr).

Die eigentliche ECU-Normierung und Folgeperioden liegen in ``logic.prices``.
"""

from __future__ import annotations

from typing import Sequence

from ecu_simulation.logic.observations import BOUNDARY_KEYS


def initial_weights_uniform(n: int) -> list[float]:
    """
    Erzeugt ``n`` gleich große Gewichte (Summe 1), z. B. für Start-Schattenpreise.

    Jedes Gewicht ist ``1/n``.
    """
    return [1.0 / n] * n


def prices_from_weights(
    vej: dict[str, float],
    ecu_per_year: float,
    weights: Sequence[float],
) -> dict[str, float]:
    """
    Baut den Start-Schattenpreis je Grenze aus relativen Gewichten und Jahres-ECU-Budget.

    Formel pro Grenze *i*: ``p_i = w_i · ecu_per_year / VEJ_i``, wobei die Eingabe-
    gewichte zuerst auf Summe 1 normiert werden (``Σ w_i = 1``).

    ``ecu_per_year`` ist das Ziel für die gewichtete Summe ``Σ_i p_i · VEJ_i`` nach
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
        vej_at_boundary = vej[boundary_key]
        if vej_at_boundary <= 0:
            raise ValueError(f"VEJ für {boundary_key} muss positiv sein.")
        shadow_prices[boundary_key] = (
            normalized_weights[index] * ecu_per_year / vej_at_boundary
        )
    return shadow_prices
