"""
Schattenpreise (ECU pro Einheit Kontrollvariable) mit Kopplung an die ECU-Jahresbilanz:

  Σ_i p_i · VEJ_i = EcuJ  (konfiguriertes Jahresbudget)

Ablauf ab dem zweiten Monat: Rohpreise aus der Timeline (Grenzüberschreitung → Bump/Elastizität),
dann **eine** Normierung ``Σ p·VEJ`` Richtung EcuJ in ``advance_shadow_prices`` (``scale_budget_to_ecu`` vs.
``scale_percentual_to_ecu`` mit Bündel-Referenz der zuletzt gültigen Preise). Startmonat: ``initial_shadow_prices_for_ecu``
(``Σ p·f·VEJ = EcuJ``).
"""

from __future__ import annotations

import math

from ecu.logic.exchange import ExchangeRates, rates_from_prices
from ecu.logic.initial_prices import initial_weights_uniform, prices_from_weights
from ecu.logic.observations import BOUNDARY_KEYS, MONTHS_PER_YEAR, ConsumptionTimeline
from ecu.logic.price_config import PriceConfig
from ecu.simulation.config import SimulationConfig

# --- Bundles und Skalierung Richtung Σ p·VEJ / Σ p·f·VEJ -----------------------------------------



def bundle_value(prices: dict[str, float], vej: dict[str, float]) -> float:
    """
    Wert des VEJ-Bündels zu Schattenpreisen: ``Σ_i p_i · VEJ_i`` (ECU pro Jahr).

    Entspricht dem linken Teil der ECU-Jahresbilanz, wenn ``p`` die Schattenpreise
    und ``VEJ`` die Grenzen pro Einheit sind.
    """
    return sum(prices[k] * vej[k] for k in BOUNDARY_KEYS)


def bundle_value_at_vej_fractions(prices: dict[str, float], vej: dict[str, float], fraction_of_vej: dict[str, float]) -> float:
    """
    ``Σ_i p_i · f_i · VEJ_i`` (ECU pro Jahr): Jahreswert, wenn die Nutzung je Grenze den
    Anteil ``f_i`` der VEJ beträgt (monatlich ``f_i · VET_i``).
    """
    return sum(prices[k] * fraction_of_vej[k] * vej[k] for k in BOUNDARY_KEYS)



def scale_budget_to_ecu(prices: dict[str, float], vej: dict[str, float], ecu_per_year: float) -> dict[str, float]:
    """
    Normierung auf ``Σ p·VEJ = EcuJ`` in einem exakten Schritt.

    Kein ``_clamp_scale_toward_budget`` — nur gemeinsamer Faktor ``ecu_per_year / Σ p·VEJ``.
    """
    bundle_total = bundle_value(prices, vej)
    if bundle_total <= 0:
        raise ValueError("Summe p·VEJ muss positiv sein.")
    scale_factor = ecu_per_year / bundle_total
    return {k: prices[k] * scale_factor for k in BOUNDARY_KEYS}


def scale_percentual_to_ecu(prices_new: dict[str, float], vej: dict[str, float], ecu_per_year: float, max_scale_pct_per_year: float, bundle_previous: float) -> dict[str, float]:
    """
    Rohpreise ``prices_new`` (geratene neue Verhältnisse aus der Timeline) einheitlich skalieren:
    ``p' = s · p_new`` — die **relativen** Verhältnisse der neuen Preise bleiben erhalten.

    ``bundle_previous`` ist ``Σ p_alt · VEJ`` zu den **zuletzt gültigen** Schattenpreisen (letzte Periode);
    das neue Bündel ist ``B_neu(s) = s · B_roh`` mit ``B_roh = Σ p_new · VEJ``.

    Zielrichtung ECU: ``s_ecu = ecu_per_year / B_roh``. Zusätzlich soll sich das Bündel gegenüber
    dem **alten** Bündel höchstens um ``p`` Prozent ändern (``p`` = ``max_scale_pct_per_year``):
    ``B_neu ∈ [bundle_previous·(1−p/100), bundle_previous·(1+p/100)]``, also
    ``s ∈ [bundle_previous·(1−p/100)/B_roh, bundle_previous·(1+p/100)/B_roh]``.
    Gewählt wird ``s = clamp(s_ecu, s_min, s_max)`` (ein Schritt, keine Schleife).
    """
    bundle_raw = bundle_value(prices_new, vej)
    if bundle_raw <= 0:
        raise ValueError("Summe p·VEJ der Rohpreise muss positiv sein.")
    if bundle_previous <= 0:
        raise ValueError("Referenz-Bündel Σ p_alt·VEJ muss positiv sein.")
    half_band = max_scale_pct_per_year / 100.0
    s_ecu = ecu_per_year / bundle_raw
    s_min = bundle_previous * (1.0 - half_band) / bundle_raw
    s_max = bundle_previous * (1.0 + half_band) / bundle_raw
    scale_factor = min(max(s_ecu, s_min), s_max)
    return {k: prices_new[k] * scale_factor for k in BOUNDARY_KEYS}


# --- Start- und Referenzpreise -----------------------------------------------------------------


def initial_shadow_prices_for_ecu(vej: dict[str, float], ecu_per_year: float, fraction_of_vej: dict[str, float]) -> dict[str, float]:
    """
    Start-Schattenpreise: gleiche Gewichte wie bisher (``prices_from_weights``),
    Normierung mit ``scale_to_ecu_budget_at_vej_fractions``, sodass
    ``Σ p_i · f_i · VEJ_i = ecu_per_year`` — bei ``p = p_ref`` kostet der
    Referenzkonsum ``f_i · VET_i`` genau den monatlichen ECU-Zuschlag ``EcuJ/12``.
    """
    raw = prices_from_weights(vej, ecu_per_year, initial_weights_uniform(len(BOUNDARY_KEYS)))
    return scale_to_ecu_budget_at_vej_fractions(raw, vej, ecu_per_year, fraction_of_vej)


def reference_shadow_prices_for_demand(cfg: SimulationConfig, vej: dict[str, float], ecu_per_year: float) -> dict[str, float]:
    """
    Referenzpreise für die Nachfragefunktion: Start-Schattenpreise, dann ``resolved_p_ref``.
    """
    initial = initial_shadow_prices_for_ecu(vej, ecu_per_year, cfg.resolved_start_demand())
    return cfg.resolved_p_ref(initial)

def scale_to_ecu_budget_at_vej_fractions(prices: dict[str, float], vej: dict[str, float], ecu_per_year: float, fraction_of_vej: dict[str, float]) -> dict[str, float]:
    """
    Gemeinsamer Faktor auf allen Preisen, sodass
    ``Σ_i p_i · f_i · VEJ_i = ecu_per_year`` (Referenzkonsum zu ``f_i`` füllt
    monatlich ``Σ p·c = ecu_per_year/12``, wenn ``p`` der Referenzpreisvektor ist).

    Eine exakte Normierung (Startpreise).
    """
    bundle_total = bundle_value_at_vej_fractions(prices, vej, fraction_of_vej)
    if bundle_total <= 0:
        raise ValueError("Summe p·VEJ·f muss positiv sein.")
    scale_factor = ecu_per_year / bundle_total
    return {k: prices[k] * scale_factor for k in BOUNDARY_KEYS}


# --- Timeline: Rohpreise, Auslastung, Elastizität -----------------------------------------------


def consumption_all_below_vet(consumption: dict[str, float], vet: dict[str, float], tol: float) -> bool:
    """
    Prüft, ob der Verbrauch an jeder Grenze die VET (Monats-Obergrenze) nicht übersteigt.

    Gibt ``True`` zurück, wenn für alle Grenzen ``consumption_i ≤ vet_i + tol`` gilt.
    """
    return all(consumption[k] <= vet[k] + tol for k in BOUNDARY_KEYS)


def _mean_boundary_utilization_last_interval(timeline: ConsumptionTimeline) -> float:
    """Mittel aus consumption/VET je Grenze im letzten Intervall."""
    last = timeline.last
    parts: list[float] = []
    for k in BOUNDARY_KEYS:
        v = last.vet_for(k)
        c = last.consumption_for(k)
        parts.append(c / v if v > 0.0 else 0.0)
    return sum(parts) / float(len(BOUNDARY_KEYS))


def _implied_elasticity_from_history(price_previous: float, price_last: float, consumption_previous: float, consumption_last: float, eta_clip: tuple[float, float]) -> float | None:
    """
    Schätzt die (negative) Preiselastizität aus zwei aufeinanderfolgenden Intervallen.

    Verwendet ``ln(Verbrauch_last/Verbrauch_vorher) / ln(Preis_last/Preis_vorher)``.
    Liefert ``None``, wenn die Voraussetzungen fehlen (nicht positive Werte,
    verschwindende Preisänderung) oder die Elastizität nicht negativ ist.

    Das Ergebnis wird auf ``[eta_clip[0], eta_clip[1]]`` begrenzt.
    """
    if price_previous <= 0 or price_last <= 0 or consumption_previous <= 0 or consumption_last <= 0:
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


def _implied_elasticity_ols_from_timeline(
    timeline: ConsumptionTimeline,
    boundary_key: str,
    eta_clip: tuple[float, float],
    lookback: int,
    min_points: int,
) -> float | None:
    """
    OLS-Steigung von ``ln(Konsum)`` auf ``ln(Preis)`` über die letzten ``lookback`` Intervalle
    (bei genügend gültigen positiven Preis-/Konsumpunkten). Entspricht konstanter
    Preiselastizität in Log-Log-Form. Negativität und ``eta_clip`` wie bei der Zwei-Punkt-Schätzung.
    """
    n_all = len(timeline)
    start = max(0, n_all - lookback)
    xs: list[float] = []
    ys: list[float] = []
    for idx in range(start, n_all):
        iv = timeline[idx]
        p = iv.price_for(boundary_key)
        c = iv.consumption_for(boundary_key)
        if p <= 0.0 or c <= 0.0:
            continue
        xs.append(math.log(p))
        ys.append(math.log(c))
    if len(xs) < min_points:
        return None
    n = len(xs)
    mx = sum(xs) / float(n)
    my = sum(ys) / float(n)
    num = 0.0
    den = 0.0
    for i in range(n):
        dx = xs[i] - mx
        dy = ys[i] - my
        num += dx * dy
        den += dx * dx
    if den <= 1e-30:
        return None
    elasticity = num / den
    if elasticity >= 0:
        return None
    eta_min, eta_max = eta_clip
    if elasticity < eta_min:
        elasticity = eta_min
    elif elasticity > eta_max:
        elasticity = eta_max
    return elasticity


def _implied_elasticity_for_boundary(timeline: ConsumptionTimeline, boundary_key: str, price_cfg: PriceConfig) -> float | None:
    """Zuerst OLS über Historie, sonst Zwei-Punkte-Fallback (letzte zwei Intervalle)."""
    eta = _implied_elasticity_ols_from_timeline(
        timeline,
        boundary_key,
        price_cfg.price_eta_clip,
        price_cfg.price_elasticity_history_lookback,
        price_cfg.price_elasticity_history_min_points,
    )
    if eta is not None:
        return eta
    if len(timeline) < 2:
        return None
    prev = timeline[-2]
    last = timeline.last
    return _implied_elasticity_from_history(
        prev.price_for(boundary_key),
        last.price_for(boundary_key),
        prev.consumption_for(boundary_key),
        last.consumption_for(boundary_key),
        price_cfg.price_eta_clip,
    )


def _raw_shadow_prices_from_timeline(timeline: ConsumptionTimeline) -> dict[str, float]:
    """
    Roh-Schattenpreise vor Normierung auf ``Σ p·VEJ = EcuJ``.

    Unter VET: letzte Schattenpreise unverändert. Bei Überschreitung: Bump bzw.
    elastizitätsbasierte Multiplikatoren pro Grenze (ohne anschließende Budget-Normierung).
    """
    if len(timeline) == 0:
        raise ValueError("timeline muss mindestens ein ConsumptionInterval enthalten.")

    price_cfg = timeline.price_config
    last_interval = timeline.last
    tol = price_cfg.tolerance
    default_price_multiplier = price_cfg.price_bump
    max_s = price_cfg.max_shadow_price_scale_pct_per_year
    if max_s > 0.0:
        bump_cap = 1.0 + 2.0 * (max_s / 100.0)
        default_price_multiplier = min(default_price_multiplier, bump_cap)

    vet_last = {k: last_interval.vet_for(k) for k in BOUNDARY_KEYS}
    shadow_prices_last = {k: last_interval.price_for(k) for k in BOUNDARY_KEYS}
    consumption_last = {k: last_interval.consumption_for(k) for k in BOUNDARY_KEYS}

    if consumption_all_below_vet(consumption_last, vet_last, tol):
        return {k: float(shadow_prices_last[k]) for k in BOUNDARY_KEYS}

    candidate_prices = {k: shadow_prices_last[k] for k in BOUNDARY_KEYS}
    eta_debug_parts: list[str] = []

    for boundary_key in BOUNDARY_KEYS:
        if consumption_last[boundary_key] <= vet_last[boundary_key] + tol:
            eta_debug_parts.append(f"{boundary_key}=≤VET")
            continue

        price_multiplier = default_price_multiplier
        implied_elasticity: float | None = None
        branch = "bump"
        if len(timeline) >= 2:
            implied_elasticity = _implied_elasticity_for_boundary(timeline, boundary_key, price_cfg)
            if implied_elasticity is not None:
                vet_over_consumption = vet_last[boundary_key] / consumption_last[boundary_key]
                if 0.0 < vet_over_consumption < 1.0:
                    multiplier_from_elasticity = math.exp(math.log(vet_over_consumption) / implied_elasticity)
                    mult_min, mult_max = price_cfg.price_step_multiplier_clip
                    price_multiplier = max(mult_min, min(mult_max, multiplier_from_elasticity))
                    branch = "eta"
        eta_s = "—" if implied_elasticity is None else f"{implied_elasticity:.4f}"
        eta_debug_parts.append(f"{boundary_key}:η={eta_s} mult={price_multiplier:.4f}({branch})")
        candidate_prices[boundary_key] = candidate_prices[boundary_key] * price_multiplier

    if price_cfg.price_debug_print_elasticity:
        print(
            f"[geschätzte Preiselastizität] Beobachtungsmonat={last_interval.datum}  "
            + "  ".join(eta_debug_parts)
        )
    return candidate_prices


def exchange_rates_for_shadow_prices(prices: dict[str, float]) -> ExchangeRates:
    """Tauschgrößen (ECU/Einheit) aus dem Schattenpreisvektor."""
    return rates_from_prices(prices)


def advance_shadow_prices(timeline: ConsumptionTimeline, vej: dict[str, float], fraction_of_vej: dict[str, float]) -> ConsumptionTimeline:
    """
    Legt die Schattenpreise fest, **bevor** in dieser Periode konsumiert wird.

    - **Leere Timeline** (erster Monat): ``initial_shadow_prices_for_ecu`` (``Σ p·f·VEJ = EcuJ``).
    - **Sonst**: Rohpreise aus ``_raw_shadow_prices_from_timeline``, dann Normierung auf
      ``Σ p·VEJ = EcuJ``: bei ``max_shadow_price_scale_pct_per_year > 0`` und mittlerer
      Auslastung des letzten Monats ``> 1 + p/100`` ``scale_percentual_to_ecu`` (Referenz:
      Bündel der zuletzt gültigen Preise), sonst ``scale_budget_to_ecu``.

    Setzt ``timeline.prices_for_next_consumption``.
    """
    if len(timeline) == 0:
        timeline.prices_for_next_consumption = initial_shadow_prices_for_ecu(vej, timeline.ecu_per_year, fraction_of_vej)
        return timeline

    price_cfg = timeline.price_config
    ecu_per_year = timeline.ecu_per_year
    last_interval = timeline.last
    vet_last = {k: last_interval.vet_for(k) for k in BOUNDARY_KEYS}
    vej_annual = {k: vet_last[k] * float(MONTHS_PER_YEAR) for k in BOUNDARY_KEYS}

    raw = _raw_shadow_prices_from_timeline(timeline)
    prices_last = {k: last_interval.price_for(k) for k in BOUNDARY_KEYS}
    bundle_previous = bundle_value(prices_last, vej_annual)
    mean_u = _mean_boundary_utilization_last_interval(timeline)
    max_pct = price_cfg.max_shadow_price_scale_pct_per_year
    threshold = 1.0 + max_pct / 100.0 if max_pct > 0.0 else float("inf")

    if max_pct > 0.0 and mean_u > threshold:
        timeline.prices_for_next_consumption = scale_percentual_to_ecu(raw, vej_annual, ecu_per_year, max_pct, bundle_previous)
    else:
        timeline.prices_for_next_consumption = scale_budget_to_ecu(raw, vej_annual, ecu_per_year)
    return timeline
