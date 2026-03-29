"""
Konsummenge ``consumption_quantity`` (Einheit der jeweiligen Kontrollvariable, vgl. VEJ).

Formel:

    consumption_quantity = demand_at_reference_price
        · (shadow_price / reference_shadow_price) ** price_elasticity

``demand_at_reference_price`` ist dabei die nachgefragte Menge bei ``shadow_price == reference_shadow_price``
(Verankerung der Kurve); der Rückgabewert ist die Menge zum **aktuellen** ``shadow_price``.

Voraussetzung: ``price_elasticity < 0`` (fallende Nachfrage bei höherem Preis).

Legende — Parameter von ``consumption_quantity``:

    shadow_price
        Aktueller Schattenpreis (ECU pro Einheit der Kontrollvariable).
    demand_at_reference_price
        Nachfragemenge bei Referenzpreis (Skalierung / Kurvenverschiebung; in der Simulation u. a. Wachstum).
    reference_shadow_price
        Referenz-Schattenpreis (typisch Start-Schattenpreis nach EcuJ-Normierung), > 0.
    price_elasticity
        Konstante Preiselastizität ε < 0 entlang der Kurve.

Später könnten hier Preisschwellen oder stückweise Funktionen ergänzt werden.
"""

from __future__ import annotations


# Implementierung aktuell isoelastisch: konstante Preiselastizität ``price_elasticity`` entlang der Kurve.
def consumption_quantity(
    shadow_price: float,
    demand_at_reference_price: float,
    reference_shadow_price: float,
    price_elasticity: float,
) -> float:
    """
    Nachfrage- bzw. Konsummenge zum gegebenen ``shadow_price`` (isoelastische Kurve).

    Rechnung: ``demand_at_reference_price * (shadow_price/reference_shadow_price)**price_elasticity``.
    """
    if reference_shadow_price <= 0 or shadow_price <= 0:
        raise ValueError(
            "reference_shadow_price und shadow_price müssen positiv sein."
        )
    if price_elasticity >= 0:
        raise ValueError(
            "price_elasticity muss für fallende Nachfrage negativ sein (< 0)."
        )
    quantity = demand_at_reference_price * (
        shadow_price / reference_shadow_price
    ) ** price_elasticity
    return quantity


if __name__ == "__main__":
    # Smoke: shadow_price hoch → Konsummenge sinkt (price_elasticity < 0)
    d1 = consumption_quantity(1.0, 100.0, 1.0, -0.5)
    d2 = consumption_quantity(2.0, 100.0, 1.0, -0.5)
    assert d2 < d1, (d1, d2)
