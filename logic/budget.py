"""Berechnung der erlaubten Verschmutzungseinheiten pro Jahr (BudgetJ je Grenze)."""

from __future__ import annotations


def compute_budget_J(grenze: float, vk: float, regeneration: float) -> float:
    """
    BudgetJ (Jahr) = (Grenze − VK) / Regeneration

    Erfordert Regeneration > 0. Ergebnis >= 0.
    """
    if regeneration <= 0:
        raise ValueError("Regeneration muss positiv sein.")
    return max(0.0, (grenze - vk) / regeneration)
