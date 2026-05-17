"""Laufzeit-Konfiguration: ecumenge_ziel_J, Referenzpreise, Elastizitäten, Nachfrage-Basis, Preis-Kybernetik."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping

from ecu.logic.observations import BOUNDARY_KEYS
from ecu.logic.planetary_constants import default_start_demand_by_key
from ecu.logic.price_config import PriceConfig
from ecu.simulation.consumption_budget import ConsumptionBudgetMethod

# Log-Raum-σ: typischer Monatsfaktor exp(±σ) ≈ ±1 % bei ±1σ (exp(ln 1,01) = 1,01).
_DEFAULT_LOG_NOISE_STD_FOR_CA_ONE_PERCENT: float = math.log(1.01)


@dataclass
class SimulationConfig:
    """Startwerte für ECU-Jahresziel, dynamische Anpassung, Nachfrageparameter; Preislogik in ``price``."""

    # Verteiltes ECU-Jahresvolumen (konstant): Ziel ``Σ p·VEJ-Ziel = ecumenge_ziel_J``
    # über gemeinsame Preisskalierung, nicht durch Änderung der Jahresmenge.
    ecumenge_ziel_J: float = 100_000.0
    # Referenz-Schattenpreis p_ref,i (ECU/Einh.); Fallback: Start-Schattenpreis nach Normierung auf ecumenge_ziel_J
    p_ref: Mapping[str, float] = field(default_factory=dict)
    # Konstante Preiselastizität ε_i < 0
    epsilon: Mapping[str, float] = field(default_factory=dict)
    # Anteil f_i am VEJ-Ziel: D_i(p_ref) = f_i·vet_ziel_i (Referenznachfrage; Startanker der Kurve).
    # Start-Schattenpreise (Bootstrap): ``p_i = w_i·ecumenge_budget_J/vej_ist_i`` mit jährlichem Referenz-``vej_ist_i`` =
    # ``f_i·vej_ziel_i``; ``Σ p_i·vej_ist_i = ecumenge_budget_J`` (keine Nachskalierung).
    # Fehlende Schlüssel: ``BoundaryConstants.start_demand_percent`` / 100 je Grenze in ``ALL_BOUNDARIES``.
    start_demand_of_vej: Mapping[str, float] = field(default_factory=dict)
    # Pro Periode (nach Wachstum): demand_at_reference_price *= exp(Z), Z ~ N(0, σ); σ wie Modulkonstante.
    demand_at_reference_price_log_noise_std: float = _DEFAULT_LOG_NOISE_STD_FOR_CA_ONE_PERCENT
    # Pro Periode: ε_i *= exp(Z), Z ~ N(0, σ); gleiche σ-Wahl wie Nachfrage-Rauschen.
    epsilon_log_noise_std: float = _DEFAULT_LOG_NOISE_STD_FOR_CA_ONE_PERCENT
    # Optional: RNG-Seed für reproduzierbare Läufe (None = nicht setzen)
    random_seed: int | None = None
    # Kybernetik der Schattenpreise (Schattenpreisfindung aus Timeline)
    price: PriceConfig = field(default_factory=PriceConfig)
    # Roh-Nachfrage gegen ECU-Obergrenze pro Monat: Σ p·c ≤ ecumenge_ziel_J/12 (reine ECU-Kappung, kein vej_ziel im Budget)
    consumption_budget_method: ConsumptionBudgetMethod = ConsumptionBudgetMethod.SCALE

    def resolved_p_ref(self, initial_prices: dict[str, float]) -> dict[str, float]:
        """p_ref: explizit oder Fallback auf initial normierte Schattenpreise."""
        out = dict(initial_prices)
        for k in BOUNDARY_KEYS:
            if k in self.p_ref and self.p_ref[k] > 0:
                out[k] = float(self.p_ref[k])
        return out

    def resolved_epsilon(self) -> dict[str, float]:
        default_eps = -0.4
        return {k: float(self.epsilon.get(k, default_eps)) for k in BOUNDARY_KEYS}

    def resolved_start_demand(self) -> dict[str, float]:
        defaults = default_start_demand_by_key()
        return {k: float(self.start_demand_of_vej.get(k, defaults[k])) for k in BOUNDARY_KEYS}


def default_config() -> SimulationConfig:
    return SimulationConfig()
