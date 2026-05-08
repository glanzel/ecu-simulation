"""
Verbrauchsbeobachtungen: Werte je planetarer Grenze, Zeitabschnitte und Timeline.

Pro Grenze werden Skalare in ``ConsumptionRecord`` gehalten; gebündelte
Schattenpreise und VEJ-/VET-Größen in der Simulation als ``dict[str, float]`` mit
Schlüsseln aus ``BOUNDARY_KEYS``. Siehe ``ecu/GLOSSAR.md`` (``vet_soll``, ``vej_ist``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ecu.logic.planetary_constants import ALL_BOUNDARIES
from ecu.logic.price_config import PriceConfig

# Reihenfolge = ``ALL_BOUNDARIES`` (keine feste Literal-Liste; beliebig erweiterbar).
BOUNDARY_KEYS: tuple[str, ...] = tuple(b.key for b in ALL_BOUNDARIES)

# Kalender: glatt 365 Tage pro Jahr, kein Schaltjahr
DAYS_PER_YEAR: float = 365.0
MONTHS_PER_YEAR: int = 12
DAYS_PER_MONTH: float = DAYS_PER_YEAR / float(MONTHS_PER_YEAR)


def _canonical_unit_for_boundary(key: str) -> str:
    for b in ALL_BOUNDARIES:
        if b.key == key:
            return b.consumption_unit_monthly
    return ""


@dataclass
class ConsumptionRecord:
    """Eine Kontrollvariable innerhalb eines Beobachtungsabschnitts (ein Monat)."""

    control_variable_key: str
    unit: str
    vej_ist: float
    """Beobachteter bzw. modellierter Verbrauch (pro Monat, gleiche Einheit wie ``vet_soll``)."""
    vet_soll: float
    """Kurzfristiges Soll pro Monat (``vej_ziel / 12`` am gleichen Kalenderraster)."""
    price: float
    """Schattenpreis, zu dem ``vej_ist`` gilt."""
    demand_at_reference_price: float | None = None
    """Nachfrage-Skalierung bei p_ref für diese Grenze (optional, pro Beobachtung)."""
    reference_shadow_price: float | None = None
    """Referenz-Schattenpreis p_ref (optional, pro Beobachtung)."""


@dataclass
class ConsumptionInterval:
    """Ein Zeitabschnitt (typ. ein Monat) mit Verbrauchszeilen je Grenze."""

    datum: int
    """Laufindex der Beobachtung (Monat)."""
    zeitraum_days: float
    """Länge des zugehörigen Zeitbereichs in Tagen (typ. ``DAYS_PER_MONTH``)."""
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

    def vej_ist_for(self, key: str) -> float:
        """Monatlicher Ist-Verbrauch (Verschmutzungseinheiten) aus dem Record."""
        return self.record_for_key(key).vej_ist

    def vet_soll_for(self, key: str) -> float:
        """Monatliches VET-Soll aus dem Record."""
        return self.record_for_key(key).vet_soll

    def shadow_prices_map(self) -> dict[str, float]:
        """Aktuelle Schattenpreise ``price`` dieses Intervalls."""
        return {k: self.price_for(k) for k in BOUNDARY_KEYS}

    @classmethod
    def from_observation(
        cls,
        step_index: int,
        zeitraum_days: float,
        shadow_prices: dict[str, float],
        vej_ist: dict[str, float],
        vet_soll: dict[str, float],
        demand_at_reference_price: dict[str, float] | None = None,
        reference_shadow_price: dict[str, float] | None = None,
    ) -> ConsumptionInterval:
        """Baut einen Abschnitt aus den Werten pro Grenze."""
        recs: list[ConsumptionRecord] = []
        for k in BOUNDARY_KEYS:
            d_ref = demand_at_reference_price[k] if demand_at_reference_price else None
            p_ref = reference_shadow_price[k] if reference_shadow_price else None
            recs.append(
                ConsumptionRecord(
                    control_variable_key=k,
                    unit=_canonical_unit_for_boundary(k),
                    vej_ist=vej_ist[k],
                    vet_soll=vet_soll[k],
                    price=shadow_prices[k],
                    demand_at_reference_price=d_ref,
                    reference_shadow_price=p_ref,
                )
            )
        return cls(
            datum=step_index,
            zeitraum_days=zeitraum_days,
            records=recs,
        )


@dataclass
class ConsumptionTimeline:
    """Geordnete Intervalle mit ECU-Jahresvolumen und Preis-Konfiguration (fortlaufend über die Simulation)."""

    ecumenge_ziel_J: float
    """Aktuelles Jahres-Ziel für Preisnormierung (wie ``SimulationConfig.ecumenge_ziel_J``); Ziel Σ p·VEJ-Ziel im harten Pfad."""
    price_config: PriceConfig
    ecumenge_ziel_J_konfig: float = 0.0
    """Unverändertes konfiguriertes Jahresziel (Kopie der Konfiguration) für Ratchet und harten Pfad."""
    ecumenge_ziel_sim_J: float = 0.0
    """Simuliertes langfristiges Jahresziel (Ratchet); sinkt höchstens um ``max_pct`` %/Periode bis ``ecumenge_ziel_J_konfig``."""
    prices_for_next_consumption: dict[str, float] | None = None
    """Von ``advance_shadow_prices`` gesetzt: Schattenpreise für den nächsten Konsum (leeres Timeline → Schätzstart)."""
    warmup_diag_sum_p_vet_soll_monthly: float | None = None
    """Nur Warmup-Preispfad: ``Σ_k p_k·VET-Soll_k`` (Monat); nach Auslesen durch Simulation gelöscht."""
    warmup_diag_ecumenge_ziel_sim_monthly: float | None = None
    """Nur Warmup: Referenz ``ecumenge_ziel_sim_J/12`` nach ggf. Ratchet derselben Periode."""
    ecumenge_T_override: float | None = None
    """Optional: simulierte ECU-Menge ``ecumenge_T`` für die **nächste** Periode (weicher Pfad); nach Lesen zurückgesetzt."""
    _intervals: list[ConsumptionInterval] = field(default_factory=list, repr=False)

    def append(self, interval: ConsumptionInterval) -> None:
        self._intervals.append(interval)

    def __len__(self) -> int:
        return len(self._intervals)

    def __getitem__(self, index: int) -> ConsumptionInterval:
        return self._intervals[index]

    def __iter__(self):
        return iter(self._intervals)

    @property
    def last(self) -> ConsumptionInterval:
        return self._intervals[-1]

    def take_ecumenge_T(self, ecumenge_ziel_J: float, months_per_year: int) -> float:
        """Liefert die simulierte monatliche ECU-Menge ``ecumenge_T`` und löscht ein gesetztes Override (weicher Pfad)."""
        if self.ecumenge_T_override is not None:
            cap = float(self.ecumenge_T_override)
            self.ecumenge_T_override = None
            return cap
        return ecumenge_ziel_J / float(months_per_year)
