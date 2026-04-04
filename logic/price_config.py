"""Konfiguration der Schattenpreis-Kybernetik (unabhängig von Nachfrage/ECU-Lauf)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PriceConfig:
    """Parameter für Preisschätzung aus der ConsumptionTimeline."""

    price_bump: float = 1.08
    tolerance: float = 1e-9
    price_eta_clip: tuple[float, float] = (-12.0, -0.02)
    price_step_multiplier_clip: tuple[float, float] = (1.01, 2.5)
    # Max. Schritt der Schattenpreise zum Vormonat (je Grenze, Verhältnis p_neu/p_alt in
    # [1−p/100, 1+p/100]) sowie gleiche Klemme am gemeinsamen Faktor in enforce_ecu_floor.
    # 0 = keine Begrenzung dieser Art (Normierung Σ p·VEJ wie bisher voll). Startpreise unberührt.
    max_shadow_price_scale_pct_per_year: float = 0.0
