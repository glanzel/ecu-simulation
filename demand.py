"""
Nachfragemenge ``demand_quantity`` (Einheit der jeweiligen Kontrollvariable, vgl. VEJ).

Formel (Rückgabewert):

    Nachfrage = demand_at_reference_price
                · (shadow_price / reference_shadow_price) ** price_elasticity

Voraussetzung: ``price_elasticity < 0`` (fallende Nachfrage bei höherem Preis).

Legende — Parameter von ``demand_quantity``:

    shadow_price
        Aktueller Schattenpreis (ECU pro Einheit der Kontrollvariable).
    demand_at_reference_price
        Skalierung der Kurve: Nachfrage, die sich bei ``shadow_price == reference_shadow_price``
        ergeben würde (Verschiebung der Kurve; in der Simulation u. a. Wachstum pro Periode).
    reference_shadow_price
        Referenz-Schattenpreis (typisch Start-Schattenpreis nach EcuJ-Normierung), > 0.
    price_elasticity
        Konstante Preiselastizität ε < 0 entlang der Kurve.

Später könnten hier Preisschwellen oder stückweise Funktionen ergänzt werden.
"""

from __future__ import annotations


# Implementierung aktuell isoelastisch: konstante Preiselastizität ``price_elasticity`` entlang der Kurve.
def demand_quantity(
    shadow_price: float,
    demand__quantity_at_reference_price: float,
    reference_shadow_price: float,
    price_elasticity: float,
) -> float:
    """
    Nachgefragte Menge zum gegebenen ``shadow_price``.

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
    return demand__quantity_at_reference_price * (
        shadow_price / reference_shadow_price
    ) ** price_elasticity


if __name__ == "__main__":
    # Smoke: shadow_price hoch → nachgefragte Menge sinkt (price_elasticity < 0)
    d1 = demand_quantity(1.0, 100.0, 1.0, -0.5)
    d2 = demand_quantity(2.0, 100.0, 1.0, -0.5)
    assert d2 < d1, (d1, d2)
