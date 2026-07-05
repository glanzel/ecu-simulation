"""Konfiguration der ECU-Preis-Kybernetik (unabhängig von Nachfrage/ECU-Lauf)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class PriceConfig:
    """Parameter für Preisschätzung aus der ConsumptionTimeline."""

    price_algorithm: Literal["text", "soft_path"] = "text"
    elasticity_factor_alpha: float = 0.1
    # Multiplikator pro Grenze bei BudgetT-Überschreitung (soft_path), wenn kein OLS-Zweig greift.
    preis_bump: float = 1.08
    tolerance: float = 1e-9
    preiselastizitaet_eta_clip: tuple[float, float] = (-12.0, -0.02)
    preis_schritt_multiplikator_clip: tuple[float, float] = (1.01, 2.5)
    preiselastizitaet_history_lookback: int = 12
    preisschritt_elastizitaet_ab: int = 5
    preiselastizitaet_debug_print: bool = False
    deltagesamt_pct: float = 1.0
