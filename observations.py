"""
Verbrauchsbeobachtungen: Werte je planetarer Grenze, Zeitabschnitte und Timeline.

Pro Grenze werden Skalare in ``ConsumptionRecord`` gehalten; gebündelte
Schattenpreise/Konsum/VEJ in der Simulation als ``dict[str, float]`` mit
Schlüsseln aus ``BOUNDARY_KEYS``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ecu_simulation.planetary_constants import ALL_BOUNDARIES

# Reihenfolge der Grenzen (Schlüssel) — zentral hier, damit keine Zirkelimporte mit ``config`` nötig sind
BOUNDARY_KEYS: tuple[str, ...] = ("co2", "hanpp", "nitrogen")

# Jahreslänge für ``zeitraum_days`` bei einer Simulationsperiode (ein „Jahr“)
DAYS_PER_YEAR: float = 365.25


def _canonical_unit_for_boundary(key: str) -> str:
    for b in ALL_BOUNDARIES:
        if b.key == key:
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
    """Beobachteter Konsum / Verbrauch (jährliche Rate, konsistent zu VEJ)."""
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

    def record_for_key(self, key: str) -> ConsumptionRecord:
        """Liefert den Record zur Grenze ``key`` (liefert KeyError bei Fehlen)."""
        for r in self.records:
            if r.control_variable_key == key:
                return r
        raise KeyError(f"Keine ConsumptionRecord für key={key!r}.")

    def price_for(self, key: str) -> float:
        """Schattenpreis ``p`` aus dem Record."""
        return self.record_for_key(key).price

    def consumption_for(self, key: str) -> float:
        """Konsum-/Nachfragemenge ``consumption`` aus dem Record."""
        return self.record_for_key(key).value

    def vej_for(self, key: str) -> float:
        """VEJ-Obergrenze aus dem Record."""
        return self.record_for_key(key).vej

    def set_new_price_for(self, key: str, new_price: float) -> None:
        """Setzt ``new_price`` im Record (falls Record existiert)."""
        self.record_for_key(key).new_price = new_price

    def set_new_prices_from_map(self, new_prices: dict[str, float]) -> None:
        """Schreibt ``new_price`` für alle Grenzen aus einem Schlüssel-Wert-Mapping."""
        for k in BOUNDARY_KEYS:
            self.set_new_price_for(k, new_prices[k])

    def shadow_prices_map(self) -> dict[str, float]:
        """Aktuelle Schattenpreise ``price`` dieses Intervalls."""
        return {k: self.price_for(k) for k in BOUNDARY_KEYS}

    @classmethod
    def from_observation(
        cls,
        step_index: int,
        zeitraum_days: float,
        shadow_prices: dict[str, float],
        consumption: dict[str, float],
        vej: dict[str, float],
    ) -> ConsumptionInterval:
        """Baut einen Abschnitt aus den Werten pro Grenze (ohne ``new_price``)."""
        recs: list[ConsumptionRecord] = []
        for k in BOUNDARY_KEYS:
            recs.append(
                ConsumptionRecord(
                    control_variable_key=k,
                    unit=_canonical_unit_for_boundary(k),
                    value=consumption[k],
                    vej=vej[k],
                    price=shadow_prices[k],
                    new_price=None,
                )
            )
        return cls(
            datum=step_index,
            zeitraum_days=zeitraum_days,
            records=recs,
        )


class ConsumptionTimeline:
    """Geordnete Liste von Intervallen mit Zugriff auf letztes/ vorletztes Element."""

    def __init__(self) -> None:
        self._intervals: list[ConsumptionInterval] = []

    def append(self, interval: ConsumptionInterval) -> None:
        self._intervals.append(interval)

    def __len__(self) -> int:
        return len(self._intervals)

    def __getitem__(self, index: int) -> ConsumptionInterval:
        return self._intervals[index]

    @property
    def last(self) -> ConsumptionInterval:
        return self._intervals[-1]

    def apply_new_prices_to_last(self, new_prices: dict[str, float]) -> None:
        """Schreibt ``new_price`` für alle Grenzen nur im letzten Intervall."""
        if not self._intervals:
            return
        self.last.set_new_prices_from_map(new_prices)
