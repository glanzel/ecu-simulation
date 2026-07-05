"""
Verbrauchsbeobachtungen: Werte je planetarer Grenze, Zeitabschnitte und Timeline.

Pro Grenze werden Skalare in ``ConsumptionRecord`` gehalten; gebündelte
ECU-Preise und VEJ-/BudgetT-Größen in der Simulation als ``dict[str, float]`` mit
Schlüsseln aus ``BOUNDARY_KEYS``. Siehe ``GLOSSAR.md`` (``budget_T``, ``nutzung_T``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from logic.planetary_constants import ALL_BOUNDARIES
from logic.price_config import PriceConfig

if TYPE_CHECKING:
    from logic.elasticity_factor import ElasticityFactorTracker
    from logic.quota import BoundaryQuotaStep

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
    nutzung_T: float
    """Beobachteter bzw. modellierter Verbrauch (pro Monat, gleiche Einheit wie ``budget_T``)."""
    budget_T: float
    """BudgetT pro Monat (``budget_J / 12`` am gleichen Kalenderraster)."""
    ecu_preis: float
    """ECU-Preis, zu dem ``nutzung_T`` gilt."""
    demand_at_reference_price: float | None = None
    """Nachfrage-Skalierung bei p_ref für diese Grenze (optional, pro Beobachtung)."""
    reference_ecu_preis: float | None = None
    """Referenz-ECU-Preis p_ref (optional, pro Beobachtung)."""


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

    def ecu_preis_for(self, key: str) -> float:
        """ECU-Preis ``p`` aus dem Record."""
        return self.record_for_key(key).ecu_preis

    def nutzung_T_for(self, key: str) -> float:
        """Monatlicher Ist-Verbrauch (Verschmutzungseinheiten) aus dem Record."""
        return self.record_for_key(key).nutzung_T

    def budget_T_for(self, key: str) -> float:
        """BudgetT (Monat) aus dem Record."""
        return self.record_for_key(key).budget_T

    def ecu_preise_map(self) -> dict[str, float]:
        """Aktuelle ECU-Preise ``price`` dieses Intervalls."""
        return {k: self.ecu_preis_for(k) for k in BOUNDARY_KEYS}

    @classmethod
    def from_observation(
        cls,
        step_index: int,
        zeitraum_days: float,
        ecu_preise: dict[str, float],
        nutzung_T: dict[str, float],
        budget_T: dict[str, float],
        demand_at_reference_price: dict[str, float] | None = None,
        reference_ecu_preis: dict[str, float] | None = None,
    ) -> ConsumptionInterval:
        """Baut einen Abschnitt aus den Werten pro Grenze."""
        recs: list[ConsumptionRecord] = []
        for k in BOUNDARY_KEYS:
            d_ref = demand_at_reference_price[k] if demand_at_reference_price else None
            p_ref = reference_ecu_preis[k] if reference_ecu_preis else None
            recs.append(
                ConsumptionRecord(
                    control_variable_key=k,
                    unit=_canonical_unit_for_boundary(k),
                    nutzung_T=nutzung_T[k],
                    budget_T=budget_T[k],
                    ecu_preis=ecu_preise[k],
                    demand_at_reference_price=d_ref,
                    reference_ecu_preis=p_ref,
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

    ecumenge_ziel: float
    """Aktuelles Jahres-Ziel für Preisnormierung (wie ``SimulationConfig.ecumenge_ziel``); Ziel Σ ecu_preis·BudgetJ-Ziel im harten Pfad."""
    price_config: PriceConfig
    ecumenge_ziel_konfig: float = 0.0
    """Unverändertes konfiguriertes Jahresziel (Kopie der Konfiguration) für Ratchet und harten Pfad."""
    ecumenge_ziel_sim: float = 0.0
    """Simuliertes langfristiges Jahresziel (Ratchet); sinkt höchstens um ``max_pct`` %/Periode bis ``ecumenge_ziel_konfig``."""
    ecu_preise_for_next_consumption: dict[str, float] | None = None
    """Von ``advance_ecu_preise`` gesetzt: ECU-Preise für den nächsten Konsum (leeres Timeline → Schätzstart)."""
    warmup_diag_sum_ecu_preis_budget_T_monthly: float | None = None
    """Nur Warmup-Preispfad: ``Σ_k p_k·budget_T_k``; nach Auslesen durch Simulation gelöscht."""
    warmup_diag_ecumenge_ziel_sim_monthly: float | None = None
    """Nur Warmup: Referenz ``ecumenge_ziel_sim/12`` nach ggf. Ratchet derselben Periode."""
    ecumenge_T_override: float | None = None
    """Optional: simulierte ECU-Menge ``ecumenge_T`` für die **nächste** Periode (weicher Pfad); nach Lesen zurückgesetzt."""
    last_quota: BoundaryQuotaStep | None = None
    """Letzter QuoteT-/DeltaT-Schritt (Text-Algorithmus, Diagnose)."""
    elasticity_factor_tracker: ElasticityFactorTracker | None = None
    """Kybernetischer Elastikfaktor je Grenze (Text-Algorithmus)."""
    quote_absenkung_f: float = 0.0
    """Kumulierter Absenkungsfortschritt f (0…1) für Quote_t; steigt pro Schritt um Deltagesamt solange Gesamtauslastung > 1."""
    last_elastikfaktor: dict[str, float] | None = None
    """Auf die Preise dieser Periode angewendeter Elastikfaktor je Grenze (Text ab Preisschritt 5)."""
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

    def take_ecumenge_T(self, ecumenge_ziel: float, months_per_year: int) -> float:
        """Liefert die simulierte monatliche ECU-Menge ``ecumenge_T`` und löscht ein gesetztes Override (weicher Pfad)."""
        if self.ecumenge_T_override is not None:
            cap = float(self.ecumenge_T_override)
            self.ecumenge_T_override = None
            return cap
        return ecumenge_ziel / float(months_per_year)
