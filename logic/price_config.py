"""Konfiguration der Schattenpreis-Kybernetik (unabhängig von Nachfrage/ECU-Lauf)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PriceConfig:
    """Parameter für Preisschätzung aus der ConsumptionTimeline."""

    # Multiplikator pro Grenze bei VET-Überschreitung, wenn kein Elastizitäts-Zweig greift.
    # Ist max_shadow_price_scale_pct_per_year > 0, wird der verwendete Wert auf 1 + 2·(max/100) gekappt.
    price_bump: float = 1.08
    tolerance: float = 1e-9
    price_eta_clip: tuple[float, float] = (-12.0, -0.02)
    price_step_multiplier_clip: tuple[float, float] = (1.01, 2.5)
    # Elastizität für den Rohpreis-Schritt: OLS ln(c) ~ const + η·ln(p) über die letzten
    # ``price_elasticity_history_lookback`` Intervalle (mindestens ``price_elasticity_history_min_points``
    # gültige Punkte); sonst Fallback Zwei-Punkte-Schätzung aus dem letzten Intervallpaar.
    price_elasticity_history_lookback: int = 12
    price_elasticity_history_min_points: int = 4
    price_debug_print_elasticity: bool = False
    # Wenn > 0 und mittlere Auslastung (letzter Monat) > 1 + p/100: Rohpreise einheitlich skalieren
    # (Verhältnisse erhalten) mit s=clamp(ecu/B_roh, B_alt·(1±p/100)/B_roh); B_alt = Σ p_alt·VEJ
    # zuletzt gültig, B_roh = Σ p_roh·VEJ; sonst exakte Normierung in einem Schritt.
    # 0 = immer exakte Normierung. Startpreise (f·VEJ) unberührt.
    max_shadow_price_scale_pct_per_year: float = 0.0
