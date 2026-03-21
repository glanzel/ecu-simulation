"""
Aggregierte Nachfrage D_i(p_i) mit konstanter Preiselastizität.

D_i = D0_i * (p_i / p_ref_i)^ε_i,  ε_i < 0

Später könnten hier Preisschwellen oder stückweise Funktionen ergänzt werden.
"""

from __future__ import annotations


def demand_constant_elasticity(
    price: float,
    d0: float,
    p_ref: float,
    epsilon: float,
) -> float:
    """
    Isoelastische Nachfrage; p_ref > 0, price > 0.
    """
    if p_ref <= 0 or price <= 0:
        raise ValueError("p_ref und price müssen positiv sein.")
    if epsilon >= 0:
        raise ValueError("Elastizität muss für fallende Nachfrage negativ sein (ε < 0).")
    return d0 * (price / p_ref) ** epsilon


if __name__ == "__main__":
    # Smoke: fallende Nachfrage bei steigendem Preis
    d1 = demand_constant_elasticity(1.0, 100.0, 1.0, -0.5)
    d2 = demand_constant_elasticity(2.0, 100.0, 1.0, -0.5)
    assert d2 < d1, (d1, d2)
