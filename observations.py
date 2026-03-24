"""
Verbrauchsbeobachtungen: zeitliche Abschnitte (ConsumptionInterval) und Timeline.

Die Simulation schreibt Intervalle; die Preisberechnung liest die Timeline und setzt
ausschließlich ``ConsumptionRecord.new_price``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ecu_simulation.config import BOUNDARY_KEYS
from ecu_simulation.planetary_constants import ALL_BOUNDARIES

# Jahreslänge für ``zeitraum_days`` bei einer Simulationsperiode (ein „Jahr“)
DAYS_PER_YEAR: float = 365.25


def _canonical_unit_for_boundary(key: str) -> str:
    for b in ALL_BOUNDARIES:
        if b.key == key:
            # Kurzform für Anzeige; ausführlicher Text in unit_note
            if key == "co2":
                return "Gt CO₂ a⁻¹"
            if key == "hanpp":
                return "Anteil (0–1), a⁻¹-skalierter Fluss wie VEJ"
            if key == "nitrogen":
                return "Tg N a⁻¹"
            return b.unit_note[:40]
    return ""


@dataclass
class ConsumptionRecord:
    """Eine Kontrollvariable innerhalb eines Beobachtungsabschnitts."""

    control_variable_key: str
    unit: str
    value: float
    """Beobachtete Nachfrage / Verbrauch (jährliche Rate, konsistent zu VEJ)."""
    vej: float
    price: float
    """Schattenpreis, zu dem ``value`` beobachtet wurde."""
    new_price: float | None = None
    """Nur von der Preisberechnung gesetzt: Vorschlag für den nächsten Schattenpreis (nach EcuJ-Boden)."""


@dataclass
class ConsumptionInterval:
    """Ein Zeitabschnitt mit Verbrauchszeilen je Grenze."""

    datum: int
    """Laufindex der Beobachtung (z. B. Schritt in der Gleichgewichtssuche)."""
    zeitraum_days: float
    """Länge des zugehörigen Zeitbereichs in Tagen (z. B. DAYS_PER_YEAR pro Simulationsjahr)."""
    records: list[ConsumptionRecord] = field(default_factory=list)


ConsumptionTimeline = list[ConsumptionInterval]


def consumption_interval_from_observation(
    step_index: int,
    zeitraum_days: float,
    prices: dict[str, float],
    demand: dict[str, float],
    vej: dict[str, float],
) -> ConsumptionInterval:
    """Baut einen Abschnitt aus den Dicts der Simulation (ohne ``new_price``)."""
    recs: list[ConsumptionRecord] = []
    for k in BOUNDARY_KEYS:
        recs.append(
            ConsumptionRecord(
                control_variable_key=k,
                unit=_canonical_unit_for_boundary(k),
                value=demand[k],
                vej=vej[k],
                price=prices[k],
                new_price=None,
            )
        )
    return ConsumptionInterval(
        datum=step_index,
        zeitraum_days=zeitraum_days,
        records=recs,
    )


def apply_new_prices_to_last_interval(
    timeline: ConsumptionTimeline,
    new_prices: dict[str, float],
) -> None:
    """Schreibt ``new_price`` auf die Records des letzten Intervalls (nur Preisfeld)."""
    if not timeline:
        return
    by_key = {r.control_variable_key: r for r in timeline[-1].records}
    for k, pv in new_prices.items():
        if k in by_key:
            by_key[k].new_price = pv
