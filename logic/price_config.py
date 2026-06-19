"""Konfiguration der Schattenpreis-Kybernetik (unabhängig von Nachfrage/ECU-Lauf)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PriceConfig:
    """Parameter für Preisschätzung aus der ConsumptionTimeline."""

    # Multiplikator pro Grenze bei VET-Überschreitung, wenn kein Elastizitäts-Zweig greift.
    # Ist max_shadow_bundle_scale_pct_per_period > 0, wird der verwendete Wert auf 1 + 2·(max/100) gekappt.
    price_bump: float = 1.08
    tolerance: float = 1e-9
    price_eta_clip: tuple[float, float] = (-12.0, -0.02)
    price_step_multiplier_clip: tuple[float, float] = (1.01, 2.5)
    # OLS ln(c) ~ const + η·ln(p) über die letzten ``price_elasticity_history_lookback`` Intervalle.
    # Erst ab ``price_elasticity_warmup_months`` abgeschlossenen Monaten: Elastizität überhaupt;
    # zugleich Mindestzahl gültiger (ln p, ln c)-Punkte in diesem Fenster — sonst Bump (+ weiche Staffel).
    price_elasticity_history_lookback: int = 12
    price_elasticity_warmup_months: int = 5
    price_debug_print_elasticity: bool = False
    # Prozent p pro Periode: im **harten** ECU-Pfad begrenzt dies ``Σ p·VEJ-Ziel`` (``scale_percentual_to_ecu``).
    # Im **Warmup** (weniger als ``price_elasticity_warmup_months`` abgeschlossene Beobachtungen,
    # bei ``max_pct > 0``): nur pro-Grenzen-Klemme ``r_k`` ggü. ``p_alt``, **keine** Normierung
    # ``Σ p·VEJ-Ziel = ecumenge_ziel_J``; bei hoher Auslastung wie weicher Pfad Ratchet auf ``ecumenge_ziel_sim_J``.
    # Nach Warmup, **weicher** ECU-Pfad (Auslastung > 1+p/100): Ratchet + ``scale_budget_to_ecu``.
    max_shadow_bundle_scale_pct_per_period: float = 1.0
