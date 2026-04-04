"""
Schattenpreise (ECU pro Einheit Kontrollvariable) mit Kopplung an die ECU-Jahresbilanz:

  Σ_i p_i · VEJ_i = EcuJ  (konfiguriertes Jahresbudget)

Konvention: Pro Grenze ein ``float`` in ``dict[str, float]``; Schlüssel entsprechen
``BOUNDARY_KEYS``. Hilfsfunktionen skalieren Preise (u. a. ``enforce_ecu_floor``:
gemeinsamer Faktor auf ``Σ p·VEJ = ecu_per_year``), leiten Updates
aus der Verbrauchs-Timeline ab. Das verteilte ECU-Jahresvolumen (EcuJ) ist konfiguriert
und wird **nicht** aus der Auslastung nachgeregelt.
"""

from __future__ import annotations

import math

from ecu_simulation.logic.exchange import ExchangeRates, rates_from_prices
from ecu_simulation.logic.initial_prices import initial_weights_uniform, prices_from_weights
from ecu_simulation.logic.observations import BOUNDARY_KEYS, MONTHS_PER_YEAR, ConsumptionTimeline
from ecu_simulation.simulation.config import SimulationConfig


def _bound_shadow_prices_vs_previous_interval(
    previous_prices: dict[str, float],
    proposed_prices: dict[str, float],
    max_step_pct_per_year: float,
) -> dict[str, float]:
    """
    Begrenzt je Grenze das Verhältnis ``p_neu / p_alt`` auf ``[1-p/100, 1+p/100]``.

    Wenn ``max_step_pct_per_year <= 0``, bleibt ``proposed_prices`` unverändert.

    Damit greift ``max_shadow_price_scale_pct_per_year`` nicht nur auf die gemeinsame
    Normierung in ``enforce_ecu_floor``, sondern auch auf starke Schritte aus
    Grenzüberschreitung (``price_bump``, elastische Multiplikatoren) und auf den Fall
    ``ecu/Σ p·VEJ ≈ 1``, wo die innere Klemme praktisch nichts ändert.
    """
    if max_step_pct_per_year <= 0.0:
        return proposed_prices
    p = min(max(max_step_pct_per_year, 0.0), 100.0)
    lo = 1.0 - p / 100.0
    hi = 1.0 + p / 100.0
    out: dict[str, float] = {}
    for k in BOUNDARY_KEYS:
        prev = previous_prices[k]
        prop = proposed_prices[k]
        if prev <= 0.0:
            out[k] = prop
            continue
        ratio = prop / prev
        ratio = max(lo, min(hi, ratio))
        out[k] = prev * ratio
    return out


def _clamp_scale_toward_budget(
    scale_factor: float,
    max_scale_pct_per_year: float,
) -> float:
    """
    Begrenzt den gemeinsamen Skalenfaktor Richtung Zielbudget:
    Absenkung (``< 1``) und Hochskalierung (``> 1``) jeweils höchstens um ``p`` Prozent
    gegenüber dem Eingang; ``max_scale_pct_per_year == 0`` = unbegrenzt.
    """
    if max_scale_pct_per_year <= 0.0:
        return scale_factor
    p = min(max(max_scale_pct_per_year, 0.0), 100.0)
    s = scale_factor
    if s < 1.0:
        floor_factor = 1.0 - p / 100.0
        s = max(s, floor_factor)
    elif s > 1.0:
        ceiling_factor = 1.0 + p / 100.0
        s = min(s, ceiling_factor)
    return s


def bundle_value(prices: dict[str, float], vej: dict[str, float]) -> float:
    """
    Wert des VEJ-Bündels zu Schattenpreisen: ``Σ_i p_i · VEJ_i`` (ECU pro Jahr).

    Entspricht dem linken Teil der ECU-Jahresbilanz, wenn ``p`` die Schattenpreise
    und ``VEJ`` die Grenzen pro Einheit sind.
    """
    return sum(prices[k] * vej[k] for k in BOUNDARY_KEYS)


def bundle_value_at_vej_fractions(
    prices: dict[str, float],
    vej: dict[str, float],
    fraction_of_vej: dict[str, float],
) -> float:
    """
    ``Σ_i p_i · f_i · VEJ_i`` (ECU pro Jahr): Jahreswert, wenn die Nutzung je Grenze den
    Anteil ``f_i`` der VEJ beträgt (monatlich ``f_i · VET_i``).
    """
    return sum(prices[k] * fraction_of_vej[k] * vej[k] for k in BOUNDARY_KEYS)


def scale_to_ecu_budget_at_vej_fractions(
    prices: dict[str, float],
    vej: dict[str, float],
    ecu_per_year: float,
    fraction_of_vej: dict[str, float],
) -> dict[str, float]:
    """
    Gemeinsamer Faktor auf allen Preisen, sodass
    ``Σ_i p_i · f_i · VEJ_i = ecu_per_year`` (Referenzkonsum zu ``f_i`` füllt
    monatlich ``Σ p·c = ecu_per_year/12``, wenn ``p`` der Referenzpreisvektor ist).

    Immer **eine** exakte Normierung (Startpreise; kein ``max_shadow_price_scale`` —
    der betrifft nur die iterative Σ p·VEJ-Anpassung nach Beobachtungen).
    """
    bundle_total = bundle_value_at_vej_fractions(prices, vej, fraction_of_vej)
    if bundle_total <= 0:
        raise ValueError("Summe p·VEJ·f muss positiv sein.")
    scale_factor = ecu_per_year / bundle_total
    return {k: prices[k] * scale_factor for k in BOUNDARY_KEYS}


def initial_shadow_prices_for_ecu(
    vej: dict[str, float],
    ecu_per_year: float,
    fraction_of_vej: dict[str, float],
) -> dict[str, float]:
    """
    Start-Schattenpreise: gleiche Gewichte wie bisher (``prices_from_weights``),
    Normierung mit ``scale_to_ecu_budget_at_vej_fractions``, sodass
    ``Σ p_i · f_i · VEJ_i = ecu_per_year`` — bei ``p = p_ref`` kostet der
    Referenzkonsum ``f_i · VET_i`` genau den monatlichen ECU-Zuschlag ``EcuJ/12``.
    """
    raw = prices_from_weights(vej, ecu_per_year, initial_weights_uniform(len(BOUNDARY_KEYS)))
    return scale_to_ecu_budget_at_vej_fractions(
        raw,
        vej,
        ecu_per_year,
        fraction_of_vej,
    )


def reference_shadow_prices_for_demand(
    cfg: SimulationConfig,
    vej: dict[str, float],
    ecu_per_year: float,
) -> dict[str, float]:
    """
    Referenzpreise für die Nachfragefunktion: Start-Schattenpreise, dann ``resolved_p_ref``.
    """
    initial = initial_shadow_prices_for_ecu(
        vej,
        ecu_per_year,
        cfg.resolved_d0_fraction(),
    )
    return cfg.resolved_p_ref(initial)


def scale_to_ecu_budget(
    prices: dict[str, float],
    vej: dict[str, float],
    ecu_per_year: float,
    *,
    max_scale_pct_per_year: float = 0.0,
) -> dict[str, float]:
    """
    Multipliziert alle Schattenpreise mit einem gemeinsamen Faktor Richtung
    ``Σ_i p_i · VEJ_i = ecu_per_year``.

    ``max_scale_pct_per_year == 0``: ein Schritt, exakt auf die Bilanz.

    ``max_scale_pct_per_year > 0``: **ein** Schritt; der Faktor ``ecu/Σ p·VEJ`` wird
    auf ``[1-p/100, 1+p/100]`` begrenzt (``_clamp_scale_toward_budget``). Pro Monat
    bewegt sich die Preisnormierung so nur begrenzt Richtung Ziel — keine vollständige
    Bilanz in einem Schritt. Startnormierung auf ``f·VEJ`` bleibt unabhängig davon
    (``scale_to_ecu_budget_at_vej_fractions``).
    """
    bundle_total = bundle_value(prices, vej)
    if bundle_total <= 0:
        raise ValueError("Summe p·VEJ muss positiv sein.")
    scale_factor = ecu_per_year / bundle_total
    if max_scale_pct_per_year > 0.0:
        scale_factor = _clamp_scale_toward_budget(scale_factor, max_scale_pct_per_year)
    return {k: prices[k] * scale_factor for k in BOUNDARY_KEYS}


def enforce_ecu_floor(
    prices: dict[str, float],
    vej: dict[str, float],
    ecu_per_year: float,
    _tol: float = 1e-12,
    *,
    max_scale_pct_per_year: float = 0.0,
) -> dict[str, float]:
    """
    Normiert die Schattenpreise wie ``scale_to_ecu_budget`` Richtung ``Σ p·VEJ = ecu_per_year``.

    ``_tol`` bleibt in der Signatur (Aufrufer aus der Timeline); die Normierung nutzt
    ihn nicht — bei ``max_scale_pct_per_year > 0`` gibt es ohnehin nur einen Teilschritt.

    ``max_scale_pct_per_year``: siehe ``scale_to_ecu_budget``.
    """
    return scale_to_ecu_budget(
        prices,
        vej,
        ecu_per_year,
        max_scale_pct_per_year=max_scale_pct_per_year,
    )


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
            shadow_prices_last,
            vej_annual,
            ecu_per_year,
            tol,
            max_scale_pct_per_year=price_cfg.max_shadow_price_scale_pct_per_year,
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
            candidate_prices,
            vej_annual,
            ecu_per_year,
            tol,
            max_scale_pct_per_year=price_cfg.max_shadow_price_scale_pct_per_year,
        )

    return _bound_shadow_prices_vs_previous_interval(
        shadow_prices_last,
        final_prices,
        price_cfg.max_shadow_price_scale_pct_per_year,
    )


def exchange_rates_for_shadow_prices(prices: dict[str, float]) -> ExchangeRates:
    """Tauschgrößen (ECU/Einheit) aus dem Schattenpreisvektor."""
    return rates_from_prices(prices)


def advance_shadow_prices(
    timeline: ConsumptionTimeline,
    vej: dict[str, float],
    fraction_of_vej: dict[str, float],
) -> ConsumptionTimeline:
    """
    Legt die Schattenpreise fest, **bevor** in dieser Periode konsumiert wird.

    - **Leere Timeline** (erster Monat): Startpreise über ``initial_shadow_prices_for_ecu``
      (exakte Normierung ``Σ p·f·VEJ = EcuJ`` gemäß ``fraction_of_vej``); kein vorheriger Konsum.
    - **Sonst**: ``estimate_next_prices_from_timeline`` aus dem letzten Intervall.

    Setzt ``timeline.prices_for_next_consumption`` — die Simulation liest das und
    erzeugt genau **einen** Konsum pro Periode.
    """
    if len(timeline) == 0:
        timeline.prices_for_next_consumption = initial_shadow_prices_for_ecu(
            vej,
            timeline.ecu_per_year,
            fraction_of_vej,
        )
        return timeline
    timeline.prices_for_next_consumption = estimate_next_prices_from_timeline(
        timeline
    )
    return timeline
