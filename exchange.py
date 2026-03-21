"""Tauschkurs: ECU pro physische Einheit und umgekehrt (aus Schattenpreisen p_i)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExchangeRates:
    """Pro Grenze: ECU pro Kontrollvariablen-Einheit und Einheiten pro ECU."""

    ecu_per_unit: dict[str, float]
    unit_per_ecu: dict[str, float]


def rates_from_prices(prices: dict[str, float]) -> ExchangeRates:
    ecu_per_unit = dict(prices)
    unit_per_ecu = {k: 1.0 / v for k, v in prices.items() if v > 0}
    return ExchangeRates(ecu_per_unit=ecu_per_unit, unit_per_ecu=unit_per_ecu)
