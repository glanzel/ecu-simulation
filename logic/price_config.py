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
