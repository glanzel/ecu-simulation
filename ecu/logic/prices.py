"""
Schattenpreise (ECU pro Einheit Kontrollvariable) mit Kopplung an die ECU-Jahresbilanz:

  Σ_i p_i · VEJ_i = EcuJ Soll  (konfiguriertes Jahresbudget)

Rohpreise aus der Timeline (VET-Überschreitung → Bump bzw. nach Warmup OLS-η). Danach
Normierung in ``advance_shadow_prices`` (Warmup: siehe Docstring dort).

Normierung in ``advance_shadow_prices``: **Warmup** (erste N Beobachtungen, ``max_pct > 0``): nur
pro-Grenzen-Klemme, kein ``Σ p·VEJ``-Match. **Weicher** ECU-Pfad: Ratchet + ``scale_budget_to_ecu``.
**Harter** Pfad: ``scale_percentual_to_ecu``; bei ``max_pct = 0`` direkt ``scale_budget_to_ecu``.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ecu.logic.exchange import ExchangeRates, rates_from_prices
from ecu.logic.initial_prices import (
    initial_weights_uniform,
    raw_initial_shadow_prices_from_utilization,
)
from ecu.logic.observations import BOUNDARY_KEYS, MONTHS_PER_YEAR, ConsumptionTimeline
from ecu.logic.price_config import PriceConfig

if TYPE_CHECKING:
    from ecu.simulation.config import SimulationConfig

# --- Bundles und Skalierung Richtung Σ p·VEJ / Σ p·f·VEJ -----------------------------------------



def bundle_p_times_vet_soll_monthly(prices: dict[str, float], vet_soll: dict[str, float]) -> float:
    """Monatlicher ECU-Wert bei voller Ausnutzung des VET-Solls: ``Σ_i p_i·VET-Soll_i``."""
    return sum(prices[k] * vet_soll[k] for k in BOUNDARY_KEYS)


def bundle_value(prices: dict[str, float], quantities: dict[str, float]) -> float:
    """
    ``Σ_i p_i · q_i`` in ECU: ``q`` z. B. ``vej_ziel`` (Jahr) oder ``vej_ist`` (Monat), konsistent zu ``p``.
    """
    return sum(prices[k] * quantities[k] for k in BOUNDARY_KEYS)


def bundle_value_at_vej_ziel_fractions(
    prices: dict[str, float], vej_ziel: dict[str, float], fraction_of_vej_ziel: dict[str, float]
) -> float:
    """
    ``Σ_i p_i · f_i · VEJ-Ziel_i`` (ECU pro Jahr); Referenzkonsum monatlich ``f_i · VET-Soll_i``.
    """
    return sum(prices[k] * fraction_of_vej_ziel[k] * vej_ziel[k] for k in BOUNDARY_KEYS)


def scale_budget_to_ecu(prices: dict[str, float], vej_ziel: dict[str, float], ecu_per_year: float) -> dict[str, float]:
    """
    Normierung auf ``Σ p·VEJ-Ziel = EcuJ`` in einem exakten Schritt.

    Kein ``_clamp_scale_toward_budget`` — nur gemeinsamer Faktor ``ecu_per_year / Σ p·VEJ-Ziel``.
    """
    bundle_total = bundle_value(prices, vej_ziel)
    if bundle_total <= 0:
        raise ValueError("Summe p·VEJ muss positiv sein.")
    scale_factor = ecu_per_year / bundle_total
    return {k: prices[k] * scale_factor for k in BOUNDARY_KEYS}


def ecu_soll_effective_after_ratchet(
    effective: float, ecu_per_year_config: float, max_scale_pct_per_period: float
) -> float:
    """Weicher Pfad: effektives Jahres-ECU-Soll sinkt höchstens um ``max_scale_pct_per_period`` %, nicht unter ``ecu_per_year_config``."""
    return max(ecu_per_year_config, effective * (1.0 - max_scale_pct_per_period / 100.0))


def mean_utilization_soft_path_threshold(max_scale_pct_per_period: float) -> float:
    """Schwelle ``mean_u > 1 + p/100`` für den weichen Pfad (``p`` = ``max_scale_pct_per_period``)."""
    if max_scale_pct_per_period <= 0.0:
        return float("inf")
    return 1.0 + max_scale_pct_per_period / 100.0


def _per_boundary_raw_multipliers_from_utilization(
    mean_utilization: float,
    utilization_by_boundary: dict[str, float],
    max_scale_pct_per_period: float,
) -> dict[str, float]:
    """
    Relativierung Überschuss Grenze vs. Gesamt: Faktor nahe 1, Abweichung skaliert mit ``max/100``.
    Bei keinem gemeinsamen Überschuss (Ø ≤ 1): überall 1. Verwendet im **harten** Pfad vor ``scale_percentual_to_ecu``.
    """
    e_ges = max(0.0, mean_utilization - 1.0)
    eps = 1e-9
    step = max_scale_pct_per_period / 100.0
    out: dict[str, float] = {}
    if e_ges <= eps:
        return {k: 1.0 for k in BOUNDARY_KEYS}
    for k in BOUNDARY_KEYS:
        e_k = max(0.0, utilization_by_boundary[k] - 1.0)
        r_k = e_k / max(eps, e_ges)
        delta = step * max(-0.5, min(2.0, r_k - 1.0))
        out[k] = 1.0 + delta
    return out


def scale_percentual_to_ecu(
    prices_new: dict[str, float],
    vej_ziel: dict[str, float],
    ecu_per_year: float,
    max_scale_pct_per_period: float,
    bundle_previous: float,
    *,
    mean_utilization: float | None = None,
    utilization_by_boundary: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    Rohpreise ``prices_new`` (geratene neue Verhältnisse aus der Timeline) einheitlich skalieren:
    ``p' = s · p_new`` — die **relativen** Verhältnisse der neuen Preise bleiben erhalten.

    ``bundle_previous`` ist ``Σ p_alt · VEJ-Ziel`` zu den **zuletzt gültigen** Schattenpreisen (letzte Periode);
    das neue Bündel ist ``B_neu(s) = s · B_roh`` mit ``B_roh = Σ p_new · VEJ-Ziel``.

    Zielrichtung ECU: ``s_ecu = ecu_per_year / B_roh``. Zusätzlich soll sich das Bündel gegenüber
    dem **vorigen Zeitschritt** höchstens um ``p`` Prozent ändern (``p`` = ``max_scale_pct_per_period``):
    ``B_neu ∈ [bundle_previous·(1−p/100), bundle_previous·(1+p/100)]``, also
    ``s ∈ [bundle_previous·(1−p/100)/B_roh, bundle_previous·(1+p/100)/B_roh]``.
    Gewählt wird ``s = clamp(s_ecu, s_min, s_max)`` (ein Schritt, keine Schleife).

    Mit ``mean_utilization`` und ``utilization_by_boundary`` werden die Rohpreise zuvor
    grenzenweise gemäß Überschuss-Relativierung modifiziert (nur **harter** Pfad).
    """
    adjusted = prices_new
    if mean_utilization is not None and utilization_by_boundary is not None:
        mult = _per_boundary_raw_multipliers_from_utilization(
            mean_utilization, utilization_by_boundary, max_scale_pct_per_period
        )
        adjusted = {k: prices_new[k] * mult[k] for k in BOUNDARY_KEYS}
    bundle_raw = bundle_value(adjusted, vej_ziel)
    if bundle_raw <= 0:
        raise ValueError("Summe p·VEJ der Rohpreise muss positiv sein.")
    if bundle_previous <= 0:
        raise ValueError("Referenz-Bündel Σ p_alt·VEJ muss positiv sein.")
    half_band = max_scale_pct_per_period / 100.0
    s_ecu = ecu_per_year / bundle_raw
    s_min = bundle_previous * (1.0 - half_band) / bundle_raw
    s_max = bundle_previous * (1.0 + half_band) / bundle_raw
    scale_factor = min(max(s_ecu, s_min), s_max)
    return {k: adjusted[k] * scale_factor for k in BOUNDARY_KEYS}


# --- Start- und Referenzpreise -----------------------------------------------------------------


def initial_shadow_prices_for_ecu(
    vej_ziel: dict[str, float], ecu_per_year_soll: float, fraction_of_vej_ziel: dict[str, float]
) -> dict[str, float]:
    """
    Start-Schattenpreise: Rohpreise aus Auslastungs-Proxy ``fraction_of_vej_ziel`` (je ``u_i``),
    Normierung mit ``scale_to_ecu_budget_at_vej_ziel_fractions``, sodass
    ``Σ p_i · f_i · VEJ-Ziel_i = ecu_per_year_soll`` — bei ``p = p_ref`` kostet der
    Referenzkonsum ``f_i · VET-Soll_i`` genau den monatlichen ECU-Zuschlag ``EcuJ/12``.
    """
    raw = raw_initial_shadow_prices_from_utilization(
        vej_ziel, ecu_per_year_soll, fraction_of_vej_ziel, initial_weights_uniform(len(BOUNDARY_KEYS))
    )
    return scale_to_ecu_budget_at_vej_ziel_fractions(raw, vej_ziel, ecu_per_year_soll, fraction_of_vej_ziel)


def reference_shadow_prices_for_demand(
    cfg: SimulationConfig, vej_ziel: dict[str, float], ecu_per_year_soll: float
) -> dict[str, float]:
    """
    Referenzpreise für die Nachfragefunktion: Start-Schattenpreise, dann ``resolved_p_ref``.
    """
    initial = initial_shadow_prices_for_ecu(vej_ziel, ecu_per_year_soll, cfg.resolved_start_demand())
    return cfg.resolved_p_ref(initial)


def scale_to_ecu_budget_at_vej_ziel_fractions(
    prices: dict[str, float], vej_ziel: dict[str, float], ecu_per_year: float, fraction_of_vej_ziel: dict[str, float]
) -> dict[str, float]:
    """
    Gemeinsamer Faktor auf allen Preisen, sodass
    ``Σ_i p_i · f_i · VEJ-Ziel_i = ecu_per_year`` (Referenzkonsum zu ``f_i`` füllt
    monatlich ``Σ p·vej_ist = ecu_per_year/12`` am Referenzpreisvektor).

    Eine exakte Normierung (Startpreise).
    """
    bundle_total = bundle_value_at_vej_ziel_fractions(prices, vej_ziel, fraction_of_vej_ziel)
    if bundle_total <= 0:
        raise ValueError("Summe p·VEJ·f muss positiv sein.")
    scale_factor = ecu_per_year / bundle_total
    return {k: prices[k] * scale_factor for k in BOUNDARY_KEYS}


# --- Timeline: Rohpreise, Auslastung, Elastizität -----------------------------------------------


def _clamp_shadow_prices_vs_last_by_utilization_share(
    prices: dict[str, float],
    prices_last: dict[str, float],
    u_by: dict[str, float],
    mean_u: float,
    max_pct: float,
) -> dict[str, float]:
    """
    Relatives Band ggü. ``prices_last``: Halbspanne
    ``r_k = (u_k · max_pct) / (mean_u · 100)`` (``max_pct`` als Prozentzahl, z. B. 1 für 1 %),
    ``prices_k`` in ``[p_alt_k·(1−r_k), p_alt_k·(1+r_k)]``.
    """
    if max_pct <= 0.0 or mean_u <= 1e-15:
        return dict(prices)
    out: dict[str, float] = {}
    for k in BOUNDARY_KEYS:
        pl = prices_last[k]
        if pl <= 0.0:
            out[k] = prices[k]
            continue
        r = (u_by[k] * max_pct) / (mean_u * 100.0)
        lo = pl * (1.0 - r)
        hi = pl * (1.0 + r)
        out[k] = min(max(prices[k], lo), hi)
    return out


def vej_ist_all_below_vet_soll(vej_ist: dict[str, float], vet_soll: dict[str, float], tol: float) -> bool:
    """
    Prüft, ob der Ist-Verbrauch an jeder Grenze das VET-Soll (Monat) nicht übersteigt.

    Gibt ``True`` zurück, wenn für alle Grenzen ``vej_ist_i ≤ vet_soll_i + tol`` gilt.
    """
    return all(vej_ist[k] <= vet_soll[k] + tol for k in BOUNDARY_KEYS)


def _mean_boundary_utilization_last_interval(timeline: ConsumptionTimeline) -> float:
    """Mittel aus VEJ-Ist / VET-Soll je Grenze im letzten Intervall."""
    last = timeline.last
    parts: list[float] = []
    for k in BOUNDARY_KEYS:
        v = last.vet_soll_for(k)
        c = last.vej_ist_for(k)
        parts.append(c / v if v > 0.0 else 0.0)
    return sum(parts) / float(len(BOUNDARY_KEYS))


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
    Preiselastizität in Log-Log-Form; Negativität und ``eta_clip`` begrenzen das Ergebnis.
    """
    n_all = len(timeline)
    start = max(0, n_all - lookback)
    xs: list[float] = []
    ys: list[float] = []
    for idx in range(start, n_all):
        iv = timeline[idx]
        p = iv.price_for(boundary_key)
        c = iv.vej_ist_for(boundary_key)
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
    """Nur OLS über die Timeline; ``None`` wenn zu wenige gültige Punkte (Schwelle = ``price_elasticity_warmup_months``, min. 2)."""
    min_pts = max(2, int(price_cfg.price_elasticity_warmup_months))
    return _implied_elasticity_ols_from_timeline(
        timeline,
        boundary_key,
        price_cfg.price_eta_clip,
        price_cfg.price_elasticity_history_lookback,
        min_pts,
    )


def _raw_shadow_prices_from_timeline(timeline: ConsumptionTimeline) -> dict[str, float]:
    """
    Roh-Schattenpreise vor Normierung auf ``Σ p·VEJ = EcuJ``.

    Unter VET: letzte Schattenpreise unverändert. Bei Überschreitung: Bump bzw. nach
    ``price_elasticity_warmup_months`` Elastizität (OLS). ECU-Normierung in ``advance_shadow_prices``.
    """
    if len(timeline) == 0:
        raise ValueError("timeline muss mindestens ein ConsumptionInterval enthalten.")

    price_cfg = timeline.price_config
    last_interval = timeline.last
    tol = price_cfg.tolerance
    default_price_multiplier = price_cfg.price_bump
    max_s = price_cfg.max_shadow_bundle_scale_pct_per_period
    if max_s > 0.0:
        bump_cap = 1.0 + 2.0 * (max_s / 100.0)
        default_price_multiplier = min(default_price_multiplier, bump_cap)

    vet_soll_last = {k: last_interval.vet_soll_for(k) for k in BOUNDARY_KEYS}
    shadow_prices_last = {k: last_interval.price_for(k) for k in BOUNDARY_KEYS}
    vej_ist_last = {k: last_interval.vej_ist_for(k) for k in BOUNDARY_KEYS}

    if vej_ist_all_below_vet_soll(vej_ist_last, vet_soll_last, tol):
        return {k: float(shadow_prices_last[k]) for k in BOUNDARY_KEYS}

    candidate_prices = {k: shadow_prices_last[k] for k in BOUNDARY_KEYS}
    eta_debug_parts: list[str] = []
    in_warmup = len(timeline) < price_cfg.price_elasticity_warmup_months

    for boundary_key in BOUNDARY_KEYS:
        if vej_ist_last[boundary_key] <= vet_soll_last[boundary_key] + tol:
            eta_debug_parts.append(f"{boundary_key}=≤VET-Soll")
            continue

        price_multiplier = default_price_multiplier
        implied_elasticity: float | None = None
        branch = "bump"
        if not in_warmup and len(timeline) >= 2:
            implied_elasticity = _implied_elasticity_for_boundary(timeline, boundary_key, price_cfg)
            if implied_elasticity is not None:
                vet_over_vej_ist = vet_soll_last[boundary_key] / vej_ist_last[boundary_key]
                if 0.0 < vet_over_vej_ist < 1.0:
                    multiplier_from_elasticity = math.exp(math.log(vet_over_vej_ist) / implied_elasticity)
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


def advance_shadow_prices(
    timeline: ConsumptionTimeline, vej_ziel: dict[str, float], fraction_of_vej_ziel: dict[str, float]
) -> ConsumptionTimeline:
    """
    Legt die Schattenpreise fest, **bevor** in dieser Periode konsumiert wird.

    - **Leere Timeline** (erster Monat): ``initial_shadow_prices_for_ecu`` (``Σ p·f·VEJ = EcuJ Soll``).
    - **Sonst**: Rohpreise aus ``_raw_shadow_prices_from_timeline``.
    - **Warmup** (``len(timeline) < price_elasticity_warmup_months`` und ``max_pct > 0``): nur
      ``_clamp_shadow_prices_vs_last_by_utilization_share`` auf den Rohpreisen (keine Normierung auf
      ``Σ p·VEJ = EcuJ``); bei hoher Auslastung wie im weichen Pfad Ratchet auf ``ecu_soll_effective``
      und ``ecu_monthly_cap_override``. Zusätzlich ``warmup_diag_*`` für ``Σ p·VET`` vs. Soll/Monat.
    - **Nach Warmup**: **weicher** Pfad bei hoher Auslastung: Ratchet + ``scale_budget_to_ecu``, sonst
      **hart** mit ``scale_percentual_to_ecu``, bzw. bei ``max_pct=0`` ``scale_budget_to_ecu``.

    Setzt ``timeline.prices_for_next_consumption``.
    """
    if len(timeline) == 0:
        timeline.ecu_monthly_cap_override = None
        timeline.prices_for_next_consumption = initial_shadow_prices_for_ecu(
            vej_ziel, timeline.ecu_per_year, fraction_of_vej_ziel
        )
        return timeline

    price_cfg = timeline.price_config
    last_interval = timeline.last
    vet_soll_last = {k: last_interval.vet_soll_for(k) for k in BOUNDARY_KEYS}
    timeline.warmup_diag_sum_p_vet_soll_monthly = None
    timeline.warmup_diag_ecu_soll_monthly = None

    raw = _raw_shadow_prices_from_timeline(timeline)
    prices_last = {k: last_interval.price_for(k) for k in BOUNDARY_KEYS}
    bundle_previous = bundle_value(prices_last, vej_ziel)
    mean_u = _mean_boundary_utilization_last_interval(timeline)
    max_pct = price_cfg.max_shadow_bundle_scale_pct_per_period
    threshold = mean_utilization_soft_path_threshold(max_pct)
    u_by = {
        k: (last_interval.vej_ist_for(k) / vet_soll_last[k]) if vet_soll_last[k] > 0.0 else 0.0
        for k in BOUNDARY_KEYS
    }

    in_warmup = len(timeline) < int(price_cfg.price_elasticity_warmup_months)
    if in_warmup and max_pct > 0.0:
        if mean_u > threshold:
            timeline.ecu_soll_effective = ecu_soll_effective_after_ratchet(
                timeline.ecu_soll_effective, timeline.ecu_per_year_config, max_pct
            )
            timeline.ecu_monthly_cap_override = timeline.ecu_soll_effective / float(MONTHS_PER_YEAR)
        else:
            timeline.ecu_monthly_cap_override = None
        p_w = _clamp_shadow_prices_vs_last_by_utilization_share(raw, prices_last, u_by, mean_u, max_pct)
        timeline.prices_for_next_consumption = p_w
        timeline.warmup_diag_sum_p_vet_soll_monthly = bundle_p_times_vet_soll_monthly(p_w, vet_soll_last)
        timeline.warmup_diag_ecu_soll_monthly = timeline.ecu_soll_effective / float(MONTHS_PER_YEAR)
        return timeline

    if max_pct > 0.0 and mean_u > threshold:
        timeline.ecu_soll_effective = ecu_soll_effective_after_ratchet(
            timeline.ecu_soll_effective, timeline.ecu_per_year_config, max_pct
        )
        timeline.ecu_monthly_cap_override = timeline.ecu_soll_effective / float(MONTHS_PER_YEAR)
        timeline.prices_for_next_consumption = scale_budget_to_ecu(
            raw, vej_ziel, timeline.ecu_soll_effective
        )
    else:
        timeline.ecu_monthly_cap_override = None
        if max_pct > 0.0:
            timeline.prices_for_next_consumption = scale_percentual_to_ecu(
                raw,
                vej_ziel,
                timeline.ecu_per_year_config,
                max_pct,
                bundle_previous,
                mean_utilization=mean_u,
                utilization_by_boundary=u_by,
            )
        else:
            timeline.prices_for_next_consumption = scale_budget_to_ecu(
                raw, vej_ziel, timeline.ecu_per_year_config
            )
    return timeline
