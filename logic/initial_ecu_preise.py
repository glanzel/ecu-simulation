"""
Start-ECU-Preise: ``p_i = w_i · ecumenge / nutzung_T_i`` (nur normierte Gewichte, keine Nachskalierung).

``nutzung_T_i`` hier der **jährliche** Referenz-Ist-Fluss (Verschmutzungseinheiten a⁻¹), im Modell
``f_i · budget_J_i`` (= ``12 · f_i · budget_T_i``). Mit ``Σ w_i = 1`` gilt
``Σ_i p_i · nutzung_T_i = ecumenge``.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from logic.observations import BOUNDARY_KEYS

_MIN_VEJ_IST_J: float = 1e-15


def initial_weights_uniform(n: int) -> list[float]:
    """
    Erzeugt ``n`` gleich große Gewichte (Summe 1), z. B. für Start-ECU-Preise.

    Jedes Gewicht ist ``1/n``.
    """
    return [1.0 / n] * n


def prices_from_weights(
    budget_J: dict[str, float],
    ecumenge_ziel: float,
    weights: Sequence[float],
) -> dict[str, float]:
    """
    Baut den Start-ECU-Preis je Grenze aus relativen Gewichten und Jahres-ECU-Budget.

    Formel pro Grenze *i*: ``p_i = w_i · ecumenge_ziel / budget_J_i``, wobei die Eingabe-
    gewichte zuerst auf Summe 1 normiert werden (``Σ w_i = 1``).

    ``ecumenge_ziel`` ist das Ziel für die gewichtete Summe ``Σ_i p_i · budget_J_i`` nach
    Normierung der Gewichte (vor weiterer Skalierung durch andere Schritte).
    """
    boundary_order = list(BOUNDARY_KEYS)
    if len(weights) != len(boundary_order):
        raise ValueError("weights passt nicht zu Grenzen.")
    weight_sum = sum(weights)
    if weight_sum <= 0:
        raise ValueError("Gewichte müssen positiv summieren.")
    normalized_weights = [wi / weight_sum for wi in weights]
    ecu_preise: dict[str, float] = {}
    for index, boundary_key in enumerate(boundary_order):
        budget_J_at = budget_J[boundary_key]
        if budget_J_at <= 0:
            raise ValueError(f"budget_J für {boundary_key} muss positiv sein.")
        ecu_preise[boundary_key] = (
            normalized_weights[index] * ecumenge_ziel / budget_J_at
        )
    return ecu_preise


def initial_ecu_preise_from_nutzung_ref_J(
    nutzung_ref_J: Mapping[str, float], ecumenge_budget_J: float, weights: Sequence[float]
) -> dict[str, float]:
    """
    ``p_i = w_i · ecumenge_budget_J / max(ε, nutzung_T_i)`` mit ``nutzung_T_i`` in **Jahres**-VE (Referenzpfad).
    Normierte Gewichte ``w_i`` (Summe 1): ``Σ_i p_i · nutzung_T_i = ecumenge_budget_J``.
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
        denom = max(_MIN_VEJ_IST_J, float(nutzung_ref_J[boundary_key]))
        out[boundary_key] = normalized_weights[index] * ecumenge_budget_J / denom
    return out
