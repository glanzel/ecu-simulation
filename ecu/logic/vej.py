"""Berechnung der erlaubten Verschmutzungseinheiten pro Jahr (VEJ-Ziel je Grenze)."""

from __future__ import annotations


def compute_vej(AG: float, VK: float, RZ: float) -> float:
    """
    VEJ-Ziel (Jahr) = (AG − VK) / RZ

    Erfordert RZ > 0. Ergebnis >= 0.
    """
    if RZ <= 0:
        raise ValueError("RZ muss positiv sein.")
    return max(0.0, (AG - VK) / RZ)
