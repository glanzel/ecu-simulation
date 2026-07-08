"""
ECU-Preise (ECU pro Einheit Kontrollvariable) mit Kopplung an die ECU-Jahresbilanz:

  Σ_i p_i · budget_J_i = ecumenge_ziel  (konfiguriertes Jahresbudget)

Rohpreise aus der Timeline (``nutzung_T`` oberhalb ``budget_T`` → Bump bzw. nach Warmup OLS-η). Danach
Normierung in ``advance_ecu_preise`` (Warmup: siehe Docstring dort).

Normierung in ``advance_ecu_preise``: **Warmup** (erste N Beobachtungen, ``max_pct > 0``): nur
pro-Grenzen-Klemme, kein ``Σ ecu_preis·BudgetJ-Ziel``-Match. **Weicher** ECU-Pfad: Ratchet + ``scale_percentual_to_ecu``
ohne Grenz-Multiplikatoren (± ``p`` % Bündel-Schritt). **Harter** Pfad: ``scale_percentual_to_ecu``
mit Überschuss-Relativierung; bei ``max_pct = 0`` direkt ``scale_budget_to_ecu``.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from logic.elasticity_factor import ElasticityFactorTracker
from logic.exchange import ExchangeRates, rates_from_prices
from logic.initial_ecu_preise import initial_ecu_preise_from_nutzung_ref_J, initial_weights_uniform
from logic.observations import BOUNDARY_KEYS, MONTHS_PER_YEAR, ConsumptionTimeline
from logic.price_config import PriceConfig
from logic.quota import QuotaCalculator

if TYPE_CHECKING:
    from simulation.config import SimulationConfig

# --- Bundles und Skalierung (Σ p·q; Startpreise: Jahresformel in ``initial_ecu_preise``) ------------



def ecu_summe_p_budget_T(prices: dict[str, float], budget_T: dict[str, float]) -> float:
    """Monatlicher ECU-Wert bei vollem Budget: ``Σ_i p_i·budget_T_i`` (``ecu_summe_p_budget_J / 12``)."""
    return sum(prices[k] * budget_T[k] for k in BOUNDARY_KEYS)


def ecu_summe_p_wert(prices: dict[str, float], quantities: dict[str, float]) -> float:
    """``Σ_i p_i · q_i`` in ECU; ``q`` z. B. ``budget_J``, ``budget_T``, ``nutzung_T`` oder ``quote_T``."""
    return sum(prices[k] * quantities[k] for k in BOUNDARY_KEYS)


def scale_budget_to_ecu(prices: dict[str, float], budget_J: dict[str, float], ecumenge_ziel: float) -> dict[str, float]:
    """
    Normierung auf ``Σ ecu_preis·BudgetJ-Ziel = ecumenge_ziel`` in einem exakten Schritt.

    Kein ``_clamp_scale_toward_budget`` — nur gemeinsamer Faktor ``ecumenge_ziel / Σ ecu_preis·BudgetJ-Ziel``.
    """
    ecu_summe_p_budget_J_total = ecu_summe_p_wert(prices, budget_J)
    if ecu_summe_p_budget_J_total <= 0:
        raise ValueError("Summe p·BudgetJ muss positiv sein.")
    scale_factor = ecumenge_ziel / ecu_summe_p_budget_J_total
    return {k: prices[k] * scale_factor for k in BOUNDARY_KEYS}


def ratchet_ecumenge_ziel_sim(
    ecumenge_ziel_sim: float, ecumenge_ziel_konfig: float, max_scale_pct_per_period: float
) -> float:
    """Weicher Pfad: simuliertes Jahresziel sinkt höchstens um ``max_scale_pct_per_period`` %, nicht unter ``ecumenge_ziel_konfig``."""
    return max(ecumenge_ziel_konfig, ecumenge_ziel_sim * (1.0 - max_scale_pct_per_period / 100.0))


def gesamtauslastung_soft_path_threshold(max_scale_pct_per_period: float) -> float:
    """Schwelle ``gesamtauslastung > 1 + p/100`` für den weichen Pfad (``p`` = ``max_scale_pct_per_period``)."""
    if max_scale_pct_per_period <= 0.0:
        return float("inf")
    return 1.0 + max_scale_pct_per_period / 100.0


def _per_boundary_raw_multipliers_from_auslastung(
    gesamtauslastung: float,
    auslastung: dict[str, float],
    max_scale_pct_per_period: float,
) -> dict[str, float]:
    """
    Relativierung Überschuss Grenze vs. Gesamt: Faktor nahe 1, Abweichung skaliert mit ``max/100``.
    Bei keinem gemeinsamen Überschuss (Ø ≤ 1): überall 1. Verwendet im **harten** Pfad vor ``scale_percentual_to_ecu``.
    """
    e_ges = max(0.0, gesamtauslastung - 1.0)
    eps = 1e-9
    step = max_scale_pct_per_period / 100.0
    out: dict[str, float] = {}
    if e_ges <= eps:
        return {k: 1.0 for k in BOUNDARY_KEYS}
    for k in BOUNDARY_KEYS:
        e_k = max(0.0, auslastung[k] - 1.0)
        r_k = e_k / max(eps, e_ges)
        delta = step * max(-0.5, min(2.0, r_k - 1.0))
        out[k] = 1.0 + delta
    return out


def scale_percentual_to_ecu(
    ecu_preise_new: dict[str, float],
    budget_J: dict[str, float],
    ecumenge_ziel: float,
    max_scale_pct_per_period: float,
    ecu_summe_p_budget_J_previous: float,
    *,
    gesamtauslastung: float | None = None,
    auslastung: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    Rohpreise ``ecu_preise_new`` (geratene neue Verhältnisse aus der Timeline) einheitlich skalieren:
    ``p' = s · p_new`` — die **relativen** Verhältnisse der neuen Preise bleiben erhalten.

    ``ecu_summe_p_budget_J_previous`` ist ``Σ p_alt · budget_J`` zu den **zuletzt gültigen** ECU-Preisen (letzte Periode);
    das neue Bündel ist ``B_neu(s) = s · B_roh`` mit ``B_roh = Σ p_new · budget_J``.

    Zielrichtung ECU: ``s_ecu = ecumenge_ziel / B_roh``. Zusätzlich soll sich das Bündel gegenüber
    dem **vorigen Zeitschritt** höchstens um ``p`` Prozent ändern (``p`` = ``max_scale_pct_per_period``):
    ``B_neu ∈ [ecu_summe_p_budget_J_previous·(1−p/100), ecu_summe_p_budget_J_previous·(1+p/100)]``, also
    ``s ∈ [ecu_summe_p_budget_J_previous·(1−p/100)/B_roh, ecu_summe_p_budget_J_previous·(1+p/100)/B_roh]``.
    Gewählt wird ``s = clamp(s_ecu, s_min, s_max)`` (ein Schritt, keine Schleife).

    Mit ``gesamtauslastung`` und ``auslastung`` werden die Rohpreise zuvor
    grenzenweise gemäß Überschuss-Relativierung modifiziert (nur **harter** Pfad).
    """
    adjusted = ecu_preise_new
    if gesamtauslastung is not None and auslastung is not None:
        mult = _per_boundary_raw_multipliers_from_auslastung(
            gesamtauslastung, auslastung, max_scale_pct_per_period
        )
        adjusted = {k: ecu_preise_new[k] * mult[k] for k in BOUNDARY_KEYS}
    ecu_summe_p_budget_J_raw = ecu_summe_p_wert(adjusted, budget_J)
    if ecu_summe_p_budget_J_raw <= 0:
        raise ValueError("Summe p·BudgetJ der Rohpreise muss positiv sein.")
    if ecu_summe_p_budget_J_previous <= 0:
        raise ValueError("Referenz-Bündel Σ p_alt·BudgetJ muss positiv sein.")
    half_band = max_scale_pct_per_period / 100.0
    s_ecu = ecumenge_ziel / ecu_summe_p_budget_J_raw
    s_min = ecu_summe_p_budget_J_previous * (1.0 - half_band) / ecu_summe_p_budget_J_raw
    s_max = ecu_summe_p_budget_J_previous * (1.0 + half_band) / ecu_summe_p_budget_J_raw
    scale_factor = min(max(s_ecu, s_min), s_max)
    return {k: adjusted[k] * scale_factor for k in BOUNDARY_KEYS}


def scale_to_quota_budget(
    ecu_preise: dict[str, float], quote_T: dict[str, float], ecumenge_T: float
) -> dict[str, float]:
    """Normierung: ``Σ ecu_preis_k · QuoteT_k = ecumenge_T``."""
    summe_p_quote_T = ecu_summe_p_wert(ecu_preise, quote_T)
    if summe_p_quote_T <= 0.0:
        raise ValueError("Summe ecu_preis·QuoteT muss positiv sein.")
    scale_factor = ecumenge_T / summe_p_quote_T
    return {k: ecu_preise[k] * scale_factor for k in BOUNDARY_KEYS}


def _ecu_preise_from_quota(ecumenge_T: float, quote_T: dict[str, float]) -> dict[str, float]:
    """Text: ``P_k = (EcumengeT / N) / QuoteT_k``."""
    n = float(len(BOUNDARY_KEYS))
    eps = 1e-15
    return {k: (ecumenge_T / n) / max(eps, quote_T[k]) for k in BOUNDARY_KEYS}


def _ratchet_ecumenge_T_text(ecumenge_T: float, ecumenge_ziel_T: float, deltagesamt_frac: float) -> float:
    """Text: EcumengeT sinkt pro Schritt um Deltagesamt, nicht unter EcumengeZiel/12."""
    return max(ecumenge_ziel_T, ecumenge_T * (1.0 - deltagesamt_frac))


def _advance_ecu_preise_text(
    timeline: ConsumptionTimeline, budget_J: dict[str, float], nutzung_anteil_budget: dict[str, float]
) -> ConsumptionTimeline:
    """Text-Kernpfad: Quote_t, P=EcumengeT/N/Quote_t, Elastikfaktor ab Schritt 5, Normierung auf Quote_t."""
    if len(timeline) == 0:
        timeline.ecumenge_T_override = None
        timeline.last_elastikfaktor = {k: 1.0 for k in BOUNDARY_KEYS}
        ecumenge_budget_J = timeline.ecumenge_ziel_sim if timeline.ecumenge_ziel_sim > 0.0 else timeline.ecumenge_ziel
        timeline.ecu_preise_for_next_consumption = initial_ecu_preise_for_ecu(budget_J, nutzung_anteil_budget, ecumenge_budget_J)
        return timeline

    price_cfg = timeline.price_config
    deltagesamt_frac = price_cfg.deltagesamt_pct / 100.0
    last_interval = timeline.last
    first_interval = timeline[0]
    budget_T_last = {k: last_interval.budget_T_for(k) for k in BOUNDARY_KEYS}
    nutzung_T_last = {k: last_interval.nutzung_T_for(k) for k in BOUNDARY_KEYS}
    nutzung_t0 = {k: first_interval.nutzung_T_for(k) for k in BOUNDARY_KEYS}
    quota = QuotaCalculator.from_nutzung_budget(
        nutzung_T_last, budget_T_last, nutzung_t0, timeline.quote_absenkung_f, deltagesamt_frac
    )
    timeline.last_quota = quota
    timeline.quote_absenkung_f = quota.absenkung_f

    ecumenge_ziel_T = timeline.ecumenge_ziel_konfig / float(MONTHS_PER_YEAR)
    ecumenge_T_sim = timeline.ecumenge_ziel_sim / float(MONTHS_PER_YEAR)
    if quota.absenkung:
        ecumenge_T = _ratchet_ecumenge_T_text(ecumenge_T_sim, ecumenge_ziel_T, deltagesamt_frac)
        timeline.ecumenge_ziel_sim = ecumenge_T * float(MONTHS_PER_YEAR)
    else:
        ecumenge_T = ecumenge_T_sim
    timeline.ecumenge_T_override = ecumenge_T

    raw = _ecu_preise_from_quota(ecumenge_T, quota.quote_T)
    if len(timeline) >= int(price_cfg.preisschritt_elastizitaet_ab):
        if timeline.elasticity_factor_tracker is None:
            timeline.elasticity_factor_tracker = ElasticityFactorTracker()
            timeline.elasticity_factor_tracker.initialize_from_timeline(timeline, deltagesamt_frac)
        tracker = timeline.elasticity_factor_tracker
        applied = {k: tracker.factor_for(k) for k in BOUNDARY_KEYS}
        for k in BOUNDARY_KEYS:
            raw[k] = raw[k] * applied[k]
            tracker.update_boundary(k, nutzung_T_last[k], quota.quote_T[k], price_cfg.elasticity_factor_alpha)
        timeline.last_elastikfaktor = applied
    else:
        timeline.last_elastikfaktor = {k: 1.0 for k in BOUNDARY_KEYS}
    timeline.ecu_preise_for_next_consumption = scale_to_quota_budget(raw, quota.quote_T, ecumenge_T)
    return timeline


# --- Start- und Referenzpreise -----------------------------------------------------------------


def initial_ecu_preise_for_ecu(
    budget_J: dict[str, float], nutzung_anteil_budget: dict[str, float], ecumenge_budget_J: float
) -> dict[str, float]:
    """
    Start-ECU-Preise: ``p_i = w_i · ecumenge_budget_J / nutzung_T_i`` mit jährlichem Referenz-``nutzung_T_i`` =
    ``f_i · budget_J_i`` (Startnachfrage am Jahresfluss). Normierte ``w_i = 1/n``; keine weitere Skalierung;
    ``Σ_i p_i · nutzung_T_i = ecumenge_budget_J``.
    """
    nutzung_ref_J = {k: float(nutzung_anteil_budget[k]) * float(budget_J[k]) for k in BOUNDARY_KEYS}
    return initial_ecu_preise_from_nutzung_ref_J(
        nutzung_ref_J, ecumenge_budget_J, initial_weights_uniform(len(BOUNDARY_KEYS))
    )


def reference_ecu_preise_for_demand(
    cfg: SimulationConfig, budget_J: dict[str, float], ecumenge_budget_J: float
) -> dict[str, float]:
    """
    Referenzpreise für die Nachfragefunktion: Start-ECU-Preise, dann ``resolved_p_ref``.
    """
    frac = cfg.resolved_start_demand()
    initial = initial_ecu_preise_for_ecu(budget_J, frac, ecumenge_budget_J)
    return cfg.resolved_p_ref(initial)


# --- Timeline: Rohpreise, Auslastung, Elastizität -----------------------------------------------


def _clamp_ecu_preise_vs_last_by_auslastung_share(
    prices: dict[str, float],
    ecu_preise_last: dict[str, float],
    auslastung: dict[str, float],
    gesamtauslastung: float,
    max_pct: float,
) -> dict[str, float]:
    """
    Relatives Band ggü. ``ecu_preise_last``: Halbspanne
    ``r_k = (u_k · max_pct) / (gesamtauslastung · 100)`` (``max_pct`` als Prozentzahl, z. B. 1 für 1 %),
    ``prices_k`` in ``[p_alt_k·(1−r_k), p_alt_k·(1+r_k)]``.
    """
    if max_pct <= 0.0 or gesamtauslastung <= 1e-15:
        return dict(prices)
    out: dict[str, float] = {}
    for k in BOUNDARY_KEYS:
        pl = ecu_preise_last[k]
        if pl <= 0.0:
            out[k] = prices[k]
            continue
        r = (auslastung[k] * max_pct) / (gesamtauslastung * 100.0)
        lo = pl * (1.0 - r)
        hi = pl * (1.0 + r)
        out[k] = min(max(prices[k], lo), hi)
    return out


def nutzung_T_all_below_budget_T(nutzung_T: dict[str, float], budget_T: dict[str, float], tol: float) -> bool:
    """
    Prüft, ob der Ist-Verbrauch an jeder Grenze das monatliche BudgetT nicht übersteigt.

    Gibt ``True`` zurück, wenn für alle Grenzen ``nutzung_T_i ≤ budget_T_i + tol`` gilt.
    """
    return all(nutzung_T[k] <= budget_T[k] + tol for k in BOUNDARY_KEYS)


def _gesamtauslastung_last_interval(timeline: ConsumptionTimeline) -> float:
    """Mittel aus NutzungT / BudgetT je Grenze im letzten Intervall."""
    last = timeline.last
    parts: list[float] = []
    for k in BOUNDARY_KEYS:
        v = last.budget_T_for(k)
        c = last.nutzung_T_for(k)
        parts.append(c / v if v > 0.0 else 0.0)
    return sum(parts) / float(len(BOUNDARY_KEYS))


def _geschaetzte_preiselastizitaet_ols_from_timeline(
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
        p = iv.ecu_preis_for(boundary_key)
        c = iv.nutzung_T_for(boundary_key)
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


def _geschaetzte_preiselastizitaet_for_boundary(timeline: ConsumptionTimeline, boundary_key: str, price_cfg: PriceConfig) -> float | None:
    """Nur OLS über die Timeline; ``None`` wenn zu wenige gültige Punkte (Schwelle = ``preisschritt_elastizitaet_ab``, min. 2)."""
    min_pts = max(2, int(price_cfg.preisschritt_elastizitaet_ab))
    return _geschaetzte_preiselastizitaet_ols_from_timeline(
        timeline,
        boundary_key,
        price_cfg.preiselastizitaet_eta_clip,
        price_cfg.preiselastizitaet_history_lookback,
        min_pts,
    )


def _raw_ecu_preise_from_timeline(timeline: ConsumptionTimeline) -> dict[str, float]:
    """
    Roh-ECU-Preise vor Normierung auf ``Σ ecu_preis·BudgetJ-Ziel = ecumenge_ziel``.

    Unterhalb des monatlichen BudgetTs: letzte ECU-Preise unverändert. Bei Überschreitung: Bump bzw. nach
    ``preisschritt_elastizitaet_ab`` Elastizität (OLS). ECU-Normierung in ``advance_ecu_preise``.
    """
    if len(timeline) == 0:
        raise ValueError("timeline muss mindestens ein ConsumptionInterval enthalten.")

    price_cfg = timeline.price_config
    last_interval = timeline.last
    tol = price_cfg.tolerance
    default_price_multiplier = price_cfg.preis_bump
    max_s = price_cfg.deltagesamt_pct
    if max_s > 0.0:
        bump_cap = 1.0 + 2.0 * (max_s / 100.0)
        default_price_multiplier = min(default_price_multiplier, bump_cap)

    budget_T_last = {k: last_interval.budget_T_for(k) for k in BOUNDARY_KEYS}
    ecu_preise_last = {k: last_interval.ecu_preis_for(k) for k in BOUNDARY_KEYS}
    nutzung_T_last = {k: last_interval.nutzung_T_for(k) for k in BOUNDARY_KEYS}

    if nutzung_T_all_below_budget_T(nutzung_T_last, budget_T_last, tol):
        return {k: float(ecu_preise_last[k]) for k in BOUNDARY_KEYS}

    candidate_ecu_preise = {k: ecu_preise_last[k] for k in BOUNDARY_KEYS}
    eta_debug_parts: list[str] = []
    in_warmup = len(timeline) < price_cfg.preisschritt_elastizitaet_ab

    for boundary_key in BOUNDARY_KEYS:
        if nutzung_T_last[boundary_key] <= budget_T_last[boundary_key] + tol:
            eta_debug_parts.append(f"{boundary_key}=≤BudgetT")
            continue

        price_multiplier = default_price_multiplier
        geschaetzte_preiselastizitaet: float | None = None
        branch = "bump"
        if not in_warmup and len(timeline) >= 2:
            geschaetzte_preiselastizitaet = _geschaetzte_preiselastizitaet_for_boundary(timeline, boundary_key, price_cfg)
            if geschaetzte_preiselastizitaet is not None:
                budget_T_over_nutzung_T = budget_T_last[boundary_key] / nutzung_T_last[boundary_key]
                if 0.0 < budget_T_over_nutzung_T < 1.0:
                    multiplier_from_elasticity = math.exp(math.log(budget_T_over_nutzung_T) / geschaetzte_preiselastizitaet)
                    mult_min, mult_max = price_cfg.preis_schritt_multiplikator_clip
                    price_multiplier = max(mult_min, min(mult_max, multiplier_from_elasticity))
                    branch = "eta"
        eta_s = "—" if geschaetzte_preiselastizitaet is None else f"{geschaetzte_preiselastizitaet:.4f}"
        eta_debug_parts.append(f"{boundary_key}:η={eta_s} mult={price_multiplier:.4f}({branch})")
        candidate_ecu_preise[boundary_key] = candidate_ecu_preise[boundary_key] * price_multiplier

    if price_cfg.preiselastizitaet_debug_print:
        print(
            f"[geschätzte Preiselastizität] Beobachtungsmonat={last_interval.datum}  "
            + "  ".join(eta_debug_parts)
        )
    return candidate_ecu_preise


def exchange_rates_for_ecu_preise(prices: dict[str, float]) -> ExchangeRates:
    """Tauschgrößen (ECU/Einheit) aus dem ECU-Preisvektor."""
    return rates_from_prices(prices)


def _advance_ecu_preise_soft_path(
    timeline: ConsumptionTimeline, budget_J: dict[str, float], nutzung_anteil_budget: dict[str, float]
) -> ConsumptionTimeline:
    """Weicher/harter Legacy-Pfad: Bump/OLS-η, Ratchet bei hoher Auslastung, ``scale_percentual_to_ecu``."""
    if len(timeline) == 0:
        timeline.ecumenge_T_override = None
        timeline.last_elastikfaktor = {k: 1.0 for k in BOUNDARY_KEYS}
        ecumenge_budget_J = (
            timeline.ecumenge_ziel_sim
            if timeline.ecumenge_ziel_sim > 0.0
            else timeline.ecumenge_ziel
        )
        timeline.ecu_preise_for_next_consumption = initial_ecu_preise_for_ecu(
            budget_J, nutzung_anteil_budget, ecumenge_budget_J
        )
        return timeline

    price_cfg = timeline.price_config
    last_interval = timeline.last
    budget_T_last = {k: last_interval.budget_T_for(k) for k in BOUNDARY_KEYS}
    timeline.warmup_diag_sum_ecu_preis_budget_T_monthly = None
    timeline.warmup_diag_ecumenge_ziel_sim_monthly = None

    raw = _raw_ecu_preise_from_timeline(timeline)
    ecu_preise_last = {k: last_interval.ecu_preis_for(k) for k in BOUNDARY_KEYS}
    ecu_summe_p_budget_J_previous = ecu_summe_p_wert(ecu_preise_last, budget_J)
    gesamtauslastung = _gesamtauslastung_last_interval(timeline)
    max_pct = price_cfg.deltagesamt_pct
    threshold = gesamtauslastung_soft_path_threshold(max_pct)
    auslastung = {
        k: (last_interval.nutzung_T_for(k) / budget_T_last[k]) if budget_T_last[k] > 0.0 else 0.0
        for k in BOUNDARY_KEYS
    }

    in_warmup = len(timeline) < int(price_cfg.preisschritt_elastizitaet_ab)
    if in_warmup and max_pct > 0.0:
        if gesamtauslastung > threshold:
            timeline.ecumenge_ziel_sim = ratchet_ecumenge_ziel_sim(
                timeline.ecumenge_ziel_sim, timeline.ecumenge_ziel_konfig, max_pct
            )
            timeline.ecumenge_T_override = timeline.ecumenge_ziel_sim / float(MONTHS_PER_YEAR)
        else:
            timeline.ecumenge_T_override = None
        p_w = _clamp_ecu_preise_vs_last_by_auslastung_share(raw, ecu_preise_last, auslastung, gesamtauslastung, max_pct)
        timeline.ecu_preise_for_next_consumption = p_w
        timeline.warmup_diag_sum_ecu_preis_budget_T_monthly = ecu_summe_p_budget_T(p_w, budget_T_last)
        timeline.warmup_diag_ecumenge_ziel_sim_monthly = timeline.ecumenge_ziel_sim / float(MONTHS_PER_YEAR)
        timeline.last_elastikfaktor = {k: 1.0 for k in BOUNDARY_KEYS}
        return timeline

    if max_pct > 0.0 and gesamtauslastung > threshold:
        raw_for_scale = _clamp_ecu_preise_vs_last_by_auslastung_share(raw, ecu_preise_last, auslastung, gesamtauslastung, max_pct)
        timeline.ecumenge_ziel_sim = ratchet_ecumenge_ziel_sim(
            timeline.ecumenge_ziel_sim, timeline.ecumenge_ziel_konfig, max_pct
        )
        timeline.ecumenge_T_override = timeline.ecumenge_ziel_sim / float(MONTHS_PER_YEAR)
        timeline.ecu_preise_for_next_consumption = scale_percentual_to_ecu(
            raw_for_scale,
            budget_J,
            timeline.ecumenge_ziel_sim,
            max_pct,
            ecu_summe_p_budget_J_previous,
        )
    else:
        timeline.ecumenge_T_override = None
        if max_pct > 0.0:
            timeline.ecu_preise_for_next_consumption = scale_percentual_to_ecu(
                raw,
                budget_J,
                timeline.ecumenge_ziel_konfig,
                max_pct,
                ecu_summe_p_budget_J_previous,
                gesamtauslastung=gesamtauslastung,
                auslastung=auslastung,
            )
        else:
            timeline.ecu_preise_for_next_consumption = scale_budget_to_ecu(
                raw, budget_J, timeline.ecumenge_ziel_konfig
            )
    timeline.last_elastikfaktor = {k: 1.0 for k in BOUNDARY_KEYS}
    return timeline


def advance_ecu_preise(
    timeline: ConsumptionTimeline, budget_J: dict[str, float], nutzung_anteil_budget: dict[str, float]
) -> ConsumptionTimeline:
    """
    Legt die ECU-Preise fest, **bevor** in dieser Periode konsumiert wird.

    ``price_algorithm=text`` (Standard): Quote_t Absenkung/Zielphase (``logic.quota``), ``P_k = EcumengeT/N/Quote_t_k``,
    Elastikfaktor ab Schritt 5, Normierung ``Σ P·Quote_t = EcumengeT``.

    ``price_algorithm=soft_path``: Legacy Bump/OLS-η mit Ratchet und ``scale_percentual_to_ecu``.
    """
    if timeline.price_config.price_algorithm == "soft_path":
        return _advance_ecu_preise_soft_path(timeline, budget_J, nutzung_anteil_budget)
    return _advance_ecu_preise_text(timeline, budget_J, nutzung_anteil_budget)
