"""
Schattenpreise (ECU pro Einheit Kontrollvariable) mit Kopplung an die ECU-Jahresbilanz:

  EcuJ ≤ Σ_i p_i · VEJ_i

Konvention: Pro Grenze ein ``float`` in ``dict[str, float]``; Schlüssel entsprechen
``BOUNDARY_KEYS``. Hilfsfunktionen normieren/skalierten Preise, leiten Updates aus
der Verbrauchs-Timeline ab, passen das verteilte ECU-Jahresvolumen an die Auslastung
an oder prüfen VEJ-Einhaltung.
"""

from __future__ import annotations

import math
from typing import Sequence

from ecu_simulation.logic.observations import BOUNDARY_KEYS, ConsumptionTimeline
from ecu_simulation.simulation.config import SimulationConfig


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


def bundle_value(prices: dict[str, float], vej: dict[str, float]) -> float:
    """
    Wert des VEJ-Bündels zu Schattenpreisen: ``Σ_i p_i · VEJ_i`` (ECU pro Jahr).

    Entspricht dem linken Teil der ECU-Jahresbilanz, wenn ``p`` die Schattenpreise
    und ``VEJ`` die Grenzen pro Einheit sind.
    """
    return sum(prices[k] * vej[k] for k in BOUNDARY_KEYS)


def scale_to_ecu_budget(
    prices: dict[str, float],
    vej: dict[str, float],
    ecu_per_year: float,
) -> dict[str, float]:
    """
    Multipliziert alle Schattenpreise mit einem gemeinsamen Faktor, sodass
    ``Σ_i p_i · VEJ_i = ecu_per_year`` gilt.

    Nützlich, um nach relativen Preisänderungen das ECU-Jahresbudget exakt
    einzuhalten.
    """
    bundle_total = bundle_value(prices, vej)
    if bundle_total <= 0:
        raise ValueError("Summe p·VEJ muss positiv sein.")
    scale_factor = ecu_per_year / bundle_total
    return {k: prices[k] * scale_factor for k in BOUNDARY_KEYS}


def enforce_ecu_floor(
    prices: dict[str, float],
    vej: dict[str, float],
    ecu_floor: float,
    tol: float = 1e-12,
) -> dict[str, float]:
    """
    Sichert die Mindestbilanz ``Σ p·VEJ ≥ ecu_floor`` (numerisch mit Toleranz).

    Liegt die Bündelsumme bereits bei mindestens ``ecu_floor`` (ggf. Toleranz),
    bleiben die Preise unverändert (Überschuss möglich). Liegt sie darunter, wird
    wie bei ``scale_to_ecu_budget`` auf genau ``ecu_floor`` hochskaliert.
    """
    bundle_total = bundle_value(prices, vej)
    if bundle_total <= 0:
        raise ValueError("Summe p·VEJ muss positiv sein.")
    if bundle_total + tol < ecu_floor:
        return scale_to_ecu_budget(prices, vej, ecu_floor)
    return {k: prices[k] for k in BOUNDARY_KEYS}


def next_ecu_budget(current: float, mean_u: float, cfg: SimulationConfig) -> float:
    """
    Nächstes verteiltes ECU-Jahresvolumen (EcuJ) aus aktuellem Wert und mittlerer Auslastung.

    Steigt die mittlere Auslastung über ``utilization_target``, wird das Volumen
    gesenkt; fällt sie darunter, erhöht. Anschließend Klemmung auf ``ecu_min`` /
    ``ecu_max``.

    Formel: ``nächstes = current * (1 - kappa * (mean_u - utilization_target))``.
    """
    factor = 1.0 - cfg.ecu_adjustment_kappa * (mean_u - cfg.utilization_target)
    nxt = current * factor
    return max(cfg.ecu_min, min(cfg.ecu_max, nxt))


def consumption_all_below_vej(
    consumption: dict[str, float],
    vej: dict[str, float],
    tol: float,
) -> bool:
    """
    Prüft, ob der Verbrauch an jeder Grenze die VEJ nicht übersteigt (mit Toleranz).

    Gibt ``True`` zurück, wenn für alle Grenzen ``consumption_i ≤ vej_i + tol`` gilt.
    """
    return all(consumption[k] <= vej[k] + tol for k in BOUNDARY_KEYS)


def _implied_elasticity_from_history(
    price_previous: float,
    price_last: float,
    consumption_previous: float,
    consumption_last: float,
    eta_clip: tuple[float, float],
) -> float | None:
    """
    Schätzt die (negative) Preiselastizität aus zwei aufeinanderfolgenden Intervallen.

    Verwendet ``ln(Verbrauch_last/Verbrauch_vorher) / ln(Preis_last/Preis_vorher)``.
    Liefert ``None``, wenn die Voraussetzungen fehlen (nicht positive Werte,
    verschwindende Preisänderung) oder die Elastizität nicht negativ ist.

    Das Ergebnis wird auf ``[eta_clip[0], eta_clip[1]]`` begrenzt.
    """
    if (
        price_previous <= 0
        or price_last <= 0
        or consumption_previous <= 0
        or consumption_last <= 0
    ):
        return None
    log_price_ratio = math.log(price_last / price_previous)
    if abs(log_price_ratio) < 1e-14:
        return None
    log_consumption_ratio = math.log(consumption_last / consumption_previous)
    elasticity = log_consumption_ratio / log_price_ratio
    if elasticity >= 0:
        return None
    eta_min, eta_max = eta_clip
    if elasticity < eta_min:
        elasticity = eta_min
    elif elasticity > eta_max:
        elasticity = eta_max
    return elasticity


def estimate_next_prices_from_timeline(
    timeline: ConsumptionTimeline,
    ecu_floor: float,
    cfg: SimulationConfig,
) -> dict[str, float]:
    """
    Leitet die Schattenpreise für das letzte Intervall aus Verlauf und Konfiguration ab.

    Ausgangspunkt ist das **letzte** Intervall der Timeline (VEJ, bisherige Preise,
    beobachteter Verbrauch). Liegt der Verbrauch überall unterhalb der VEJ, werden
    die Preise nur noch so angepasst, dass ``enforce_ecu_floor`` die ECU-Untergrenze
    einhält. Sonst wird pro Grenze mit Überschreitung der Preis erhöht: Standard ist
    der Faktor ``price_bump``; wenn ein vorheriges Intervall existiert, kann eine
    aus der Historie geschätzte negative Elastizität einen anderen Multiplikator
    vorschlagen (geclippt). Anschließend wieder ``enforce_ecu_floor``.

    Schreibt die ermittelten Preise per ``apply_new_prices_to_last`` ins letzte
    Intervall und gibt denselben Vektor zurück.
    """
    if len(timeline) == 0:
        raise ValueError("timeline muss mindestens ein ConsumptionInterval enthalten.")

    last_interval = timeline.last
    tol = cfg.tolerance
    default_price_multiplier = cfg.price_bump

    vej_last = {k: last_interval.vej_for(k) for k in BOUNDARY_KEYS}
    shadow_prices_last = {k: last_interval.price_for(k) for k in BOUNDARY_KEYS}
    consumption_last = {k: last_interval.consumption_for(k) for k in BOUNDARY_KEYS}

    if consumption_all_below_vej(consumption_last, vej_last, tol):
        final_prices = enforce_ecu_floor(
            shadow_prices_last, vej_last, ecu_floor, tol
        )
    else:
        candidate_prices = {k: shadow_prices_last[k] for k in BOUNDARY_KEYS}
        has_previous_interval = len(timeline) >= 2
        previous_interval = timeline[-2] if has_previous_interval else None

        for boundary_key in BOUNDARY_KEYS:
            if consumption_last[boundary_key] <= vej_last[boundary_key] + tol:
                continue

            price_multiplier = default_price_multiplier
            if has_previous_interval and previous_interval is not None:
                price_previous = previous_interval.price_for(boundary_key)
                consumption_previous = previous_interval.consumption_for(boundary_key)

                implied_elasticity = _implied_elasticity_from_history(
                    price_previous,
                    shadow_prices_last[boundary_key],
                    consumption_previous,
                    consumption_last[boundary_key],
                    cfg.price_eta_clip,
                )
                if implied_elasticity is not None:
                    vej_over_consumption = (
                        vej_last[boundary_key] / consumption_last[boundary_key]
                    )
                    if 0.0 < vej_over_consumption < 1.0:
                        multiplier_from_elasticity = math.exp(
                            math.log(vej_over_consumption) / implied_elasticity
                        )
                        mult_min, mult_max = cfg.price_step_multiplier_clip
                        price_multiplier = max(
                            mult_min,
                            min(mult_max, multiplier_from_elasticity),
                        )
            candidate_prices[boundary_key] = (
                candidate_prices[boundary_key] * price_multiplier
            )

        final_prices = enforce_ecu_floor(
            candidate_prices, vej_last, ecu_floor, tol
        )

    timeline.apply_new_prices_to_last(final_prices)
    return final_prices


def finalize_new_prices_on_last_interval(
    timeline: ConsumptionTimeline,
    prices_after_enforce: dict[str, float],
) -> None:
    """
    Schreibt den abgeschlossenen Schattenpreisvektor nur auf das letzte Intervall.

    Dient als dünne Hilfsfunktion um ``apply_new_prices_to_last``, wenn die Preise
    bereits außerhalb dieser Datei berechnet wurden.
    """
    timeline.apply_new_prices_to_last(prices_after_enforce)
