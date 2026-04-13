"""Tauschkurs: ECU pro physische Einheit und umgekehrt (aus Schattenpreisen)."""

from __future__ import annotations

from dataclasses import dataclass

from ecu.logic.observations import BOUNDARY_KEYS


@dataclass(frozen=True)
class ExchangeRates:
    """Pro Grenze: ECU pro Kontrollvariablen-Einheit und Einheiten pro ECU."""

    ecu_per_unit: dict[str, float]
    unit_per_ecu: dict[str, float]


def rates_from_prices(prices: dict[str, float]) -> ExchangeRates:
    ecu = dict(prices)
    unit_per = {
        k: (1.0 / ecu[k] if ecu[k] > 0 else 0.0) for k in BOUNDARY_KEYS
    }
    return ExchangeRates(ecu_per_unit=ecu, unit_per_ecu=unit_per)
