"""
Start-Schattenpreise: ``p_i = w_i · ecumenge / vej_ist_i`` (nur normierte Gewichte, keine Nachskalierung).

``vej_ist_i`` hier der **jährliche** Referenz-Ist-Fluss (Verschmutzungseinheiten a⁻¹), im Modell
``f_i · vej_ziel_i`` (= ``12 · f_i · vet_ziel_i``). Mit ``Σ w_i = 1`` gilt
``Σ_i p_i · vej_ist_i = ecumenge``.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from ecu.logic.observations import BOUNDARY_KEYS

_MIN_VEJ_IST_J: float = 1e-15


def initial_weights_uniform(n: int) -> list[float]:
    """
    Erzeugt ``n`` gleich große Gewichte (Summe 1), z. B. für Start-Schattenpreise.

    Jedes Gewicht ist ``1/n``.
    """
    return [1.0 / n] * n


def prices_from_weights(
    vej_ziel: dict[str, float],
    ecumenge_ziel_J: float,
    weights: Sequence[float],
) -> dict[str, float]:
    """
    Baut den Start-Schattenpreis je Grenze aus relativen Gewichten und Jahres-ECU-Budget.

    Formel pro Grenze *i*: ``p_i = w_i · ecumenge_ziel_J / vej_ziel_i``, wobei die Eingabe-
    gewichte zuerst auf Summe 1 normiert werden (``Σ w_i = 1``).

    ``ecumenge_ziel_J`` ist das Ziel für die gewichtete Summe ``Σ_i p_i · vej_ziel_i`` nach
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
            raise ValueError(f"vej_ziel für {boundary_key} muss positiv sein.")
        shadow_prices[boundary_key] = (
            normalized_weights[index] * ecumenge_ziel_J / vej_ziel_at
        )
    return shadow_prices


def initial_shadow_prices_from_vej_ist_J(
    vej_ist_ref_J: Mapping[str, float], ecumenge_budget_J: float, weights: Sequence[float]
) -> dict[str, float]:
    """
    ``p_i = w_i · ecumenge_budget_J / max(ε, vej_ist_i)`` mit ``vej_ist_i`` in **Jahres**-VE (Referenzpfad).
    Normierte Gewichte ``w_i`` (Summe 1): ``Σ_i p_i · vej_ist_i = ecumenge_budget_J``.
    """
    boundary_order = list(BOUNDARY_KEYS)
    if len(weights) != len(boundary_order):
        raise ValueError("weights passt nicht zu Grenzen.")
    weight_sum = sum(weights)
    if weight_sum <= 0:
        raise ValueError("Gewichte müssen positiv summieren.")
    normalized_weights = [wi / weight_sum for wi in weights]
    if ecumenge_budget_J <= 0:
        raise ValueError("ecumenge_budget_J muss positiv sein.")
    out: dict[str, float] = {}
    for index, boundary_key in enumerate(boundary_order):
        denom = max(_MIN_VEJ_IST_J, float(vej_ist_ref_J[boundary_key]))
        out[boundary_key] = normalized_weights[index] * ecumenge_budget_J / denom
    return out
