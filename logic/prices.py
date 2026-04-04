"""
Schattenpreise (ECU pro Einheit Kontrollvariable) mit Kopplung an die ECU-Jahresbilanz:

  EcuJ ≤ Σ_i p_i · VEJ_i

Konvention: Pro Grenze ein ``float`` in ``dict[str, float]``; Schlüssel entsprechen
``BOUNDARY_KEYS``. Hilfsfunktionen skalieren Preise (u. a. ``enforce_ecu_floor``:
gemeinsamer Faktor, sodass ``Σ p·VEJ`` die ECU-Untergrenze erreicht), leiten Updates
aus der Verbrauchs-Timeline ab. Das verteilte ECU-Jahresvolumen (EcuJ) ist konfiguriert
und wird **nicht** aus der Auslastung nachgeregelt.
"""

from __future__ import annotations

import math

from ecu_simulation.logic.exchange import ExchangeRates, rates_from_prices
from ecu_simulation.logic.initial_prices import initial_weights_uniform, prices_from_weights
from ecu_simulation.logic.observations import BOUNDARY_KEYS, MONTHS_PER_YEAR, ConsumptionTimeline
from ecu_simulation.simulation.config import SimulationConfig


def bundle_value(prices: dict[str, float], vej: dict[str, float]) -> float:
    """
    Wert des VEJ-Bündels zu Schattenpreisen: ``Σ_i p_i · VEJ_i`` (ECU pro Jahr).

    Entspricht dem linken Teil der ECU-Jahresbilanz, wenn ``p`` die Schattenpreise
    und ``VEJ`` die Grenzen pro Einheit sind.
    """
    return sum(prices[k] * vej[k] for k in BOUNDARY_KEYS)


def initial_shadow_prices_for_ecu(vej: dict[str, float], ecu_per_year: float) -> dict[str, float]:
    """
    Start-Schattenpreise normiert auf ``ecu_per_year`` (Σ p·VEJ = ecu_per_year).

    Kombination aus gleichverteilten Gewichten und ``scale_to_ecu_budget``.
    """
    raw = prices_from_weights(vej, ecu_per_year, initial_weights_uniform(len(BOUNDARY_KEYS)))
    return scale_to_ecu_budget(raw, vej, ecu_per_year)


def reference_shadow_prices_for_demand(
    cfg: SimulationConfig,
    vej: dict[str, float],
    ecu_per_year: float,
) -> dict[str, float]:
    """
    Referenzpreise für die Nachfragefunktion: Start-Schattenpreise, dann ``resolved_p_ref``.
    """
    initial = initial_shadow_prices_for_ecu(vej, ecu_per_year)
    return cfg.resolved_p_ref(initial)


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
    ecu_per_year: float,
    tol: float = 1e-12,
) -> dict[str, float]:
    """
    Sichert die Mindestbilanz ``Σ p·VEJ ≥ ecu_per_year`` (numerisch mit Toleranz).

    Liegt die Bündelsumme bereits bei mindestens ``ecu_per_year`` (ggf. Toleranz),
    bleiben die Preise unverändert (Überschuss möglich). Liegt sie darunter, wird
    wie bei ``scale_to_ecu_budget`` auf genau ``ecu_per_year`` hochskaliert.
    """
    bundle_total = bundle_value(prices, vej)
    if bundle_total <= 0:
        raise ValueError("Summe p·VEJ muss positiv sein.")
    if bundle_total + tol < ecu_per_year:
        return scale_to_ecu_budget(prices, vej, ecu_per_year)
    return {k: prices[k] for k in BOUNDARY_KEYS}


def consumption_all_below_vet(
    consumption: dict[str, float],
    vet: dict[str, float],
    tol: float,
) -> bool:
    """
    Prüft, ob der Verbrauch an jeder Grenze die VET (Monats-Obergrenze) nicht übersteigt.

    Gibt ``True`` zurück, wenn für alle Grenzen ``consumption_i ≤ vet_i + tol`` gilt.
    """
    return all(consumption[k] <= vet[k] + tol for k in BOUNDARY_KEYS)


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


def estimate_next_prices_from_timeline(timeline: ConsumptionTimeline) -> dict[str, float]:
    """
    Leitet die Schattenpreise für den **nächsten** Konsum aus dem letzten Intervall ab.

    Nutzt ``timeline.ecu_per_year`` und ``timeline.price_config``. Rückgabe wird von
    ``advance_shadow_prices`` in ``prices_for_next_consumption`` übernommen.
    """
    if len(timeline) == 0:
        raise ValueError("timeline muss mindestens ein ConsumptionInterval enthalten.")

    price_cfg = timeline.price_config
    ecu_per_year = timeline.ecu_per_year
    last_interval = timeline.last
    tol = price_cfg.tolerance
    default_price_multiplier = price_cfg.price_bump

    vet_last = {k: last_interval.vet_for(k) for k in BOUNDARY_KEYS}
    vej_annual = {k: vet_last[k] * float(MONTHS_PER_YEAR) for k in BOUNDARY_KEYS}
    shadow_prices_last = {k: last_interval.price_for(k) for k in BOUNDARY_KEYS}
    consumption_last = {k: last_interval.consumption_for(k) for k in BOUNDARY_KEYS}

    if consumption_all_below_vet(consumption_last, vet_last, tol):
        final_prices = enforce_ecu_floor(
            shadow_prices_last, vej_annual, ecu_per_year, tol
        )
    else:
        candidate_prices = {k: shadow_prices_last[k] for k in BOUNDARY_KEYS}
        has_previous_interval = len(timeline) >= 2
        previous_interval = timeline[-2] if has_previous_interval else None

        for boundary_key in BOUNDARY_KEYS:
            if consumption_last[boundary_key] <= vet_last[boundary_key] + tol:
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
                    price_cfg.price_eta_clip,
                )
                if implied_elasticity is not None:
                    vet_over_consumption = (
                        vet_last[boundary_key] / consumption_last[boundary_key]
                    )
                    if 0.0 < vet_over_consumption < 1.0:
                        multiplier_from_elasticity = math.exp(
                            math.log(vet_over_consumption) / implied_elasticity
                        )
                        mult_min, mult_max = price_cfg.price_step_multiplier_clip
                        price_multiplier = max(
                            mult_min,
                            min(mult_max, multiplier_from_elasticity),
                        )
            candidate_prices[boundary_key] = (
                candidate_prices[boundary_key] * price_multiplier
            )

        final_prices = enforce_ecu_floor(
            candidate_prices, vej_annual, ecu_per_year, tol
        )

    return final_prices


def exchange_rates_for_shadow_prices(prices: dict[str, float]) -> ExchangeRates:
    """Tauschgrößen (ECU/Einheit) aus dem Schattenpreisvektor."""
    return rates_from_prices(prices)


def advance_shadow_prices(
    timeline: ConsumptionTimeline,
    vej: dict[str, float],
) -> ConsumptionTimeline:
    """
    Legt die Schattenpreise fest, **bevor** in dieser Periode konsumiert wird.

    - **Leere Timeline** (erster Monat): Startpreise über ``initial_shadow_prices_for_ecu``
      (Schätzung auf Basis von jährlicher VEJ und ``ecu_per_year``), kein vorheriger Konsum.
    - **Sonst**: ``estimate_next_prices_from_timeline`` aus dem letzten Intervall.

    Setzt ``timeline.prices_for_next_consumption`` — die Simulation liest das und
    erzeugt genau **einen** Konsum pro Periode.
    """
    if len(timeline) == 0:
        timeline.prices_for_next_consumption = initial_shadow_prices_for_ecu(
            vej, timeline.ecu_per_year
        )
        return timeline
    timeline.prices_for_next_consumption = estimate_next_prices_from_timeline(
        timeline
    )
    return timeline
