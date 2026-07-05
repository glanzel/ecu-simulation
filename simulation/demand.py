"""
Konsummenge ``consumption_quantity`` (Einheit der jeweiligen Kontrollvariable; in der Simulation pro Monat, vgl. VET).

Formel:

    consumption_quantity = demand_at_reference_price
        · (ecu_preis / reference_ecu_preis) ** price_elasticity

``demand_at_reference_price`` ist dabei die nachgefragte Menge bei ``ecu_preis == reference_ecu_preis``
(Verankerung der Kurve); der Rückgabewert ist die Menge zum **aktuellen** ``ecu_preis``.

Voraussetzung: ``price_elasticity < 0`` (fallende Nachfrage bei höherem Preis).

Legende — Parameter von ``consumption_quantity``:

    ecu_preis
        Aktueller ECU-Preis (ECU pro Einheit der Kontrollvariable).
    demand_at_reference_price
        Nachfragemenge bei Referenzpreis (Skalierung / Kurvenverschiebung; in der Simulation u. a. Wachstum).
    reference_ecu_preis
        Referenz-ECU-Preis (typisch Start-ECU-Preis nach Normierung auf ecumenge_ziel), > 0.
    price_elasticity
        Konstante Preiselastizität ε < 0 entlang der Kurve.

Später könnten hier Preisschwellen oder stückweise Funktionen ergänzt werden.
"""

from __future__ import annotations


# Implementierung aktuell isoelastisch: konstante Preiselastizität ``price_elasticity`` entlang der Kurve.
def consumption_quantity(
    ecu_preis: float,
    demand_at_reference_price: float,
    reference_ecu_preis: float,
    price_elasticity: float,
) -> float:
    """
    Nachfrage- bzw. Konsummenge zum gegebenen ``ecu_preis`` (isoelastische Kurve).

    Rechnung: ``demand_at_reference_price * (ecu_preis/reference_ecu_preis)**price_elasticity``.
    """
    if reference_ecu_preis <= 0 or ecu_preis <= 0:
        raise ValueError(
            "reference_ecu_preis und ecu_preis müssen positiv sein."
        )
    if price_elasticity >= 0:
        raise ValueError(
            "price_elasticity muss für fallende Nachfrage negativ sein (< 0)."
        )
    quantity = demand_at_reference_price * (
        ecu_preis / reference_ecu_preis
    ) ** price_elasticity
    return quantity


if __name__ == "__main__":
    # Smoke: ecu_preis hoch → Konsummenge sinkt (price_elasticity < 0)
    d1 = consumption_quantity(1.0, 100.0, 1.0, -0.5)
    d2 = consumption_quantity(2.0, 100.0, 1.0, -0.5)
    assert d2 < d1, (d1, d2)
