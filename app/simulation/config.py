"""Laufzeit-Konfiguration: EcuJ, Referenzpreise, Elastizitäten, Nachfrage-Basis, Preis-Kybernetik."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ecu_simulation.logic.observations import BOUNDARY_KEYS
from ecu_simulation.logic.price_config import PriceConfig
from ecu_simulation.simulation.consumption_budget import ConsumptionBudgetMethod


@dataclass
class SimulationConfig:
    """Start-EcuJ, dynamische Anpassung, Nachfrageparameter; Preislogik in ``price``."""

    # Verteiltes ECU-Jahresvolumen EcuJ (konstant): Ziel ``Σ p·VEJ = ecu_per_year``
    # über gemeinsame Preisskalierung, nicht durch Änderung von EcuJ.
    ecu_per_year: float = 100_000.0
    # Referenz-Schattenpreis p_ref,i (ECU/Einh.); Fallback: Start-Schattenpreis nach EcuJ-Normierung
    p_ref: Mapping[str, float] = field(default_factory=dict)
    # Konstante Preiselastizität ε_i < 0
    epsilon: Mapping[str, float] = field(default_factory=dict)
    # Anteil f_i der VEJ: D_i(p_ref) = f_i·VET_i (Referenznachfrage; „d0“ = Startanker der Kurve).
    # Start-Schattenpreise werden so normiert, dass Σ p·(f·VET) = EcuJ/12 (Referenzkonsum am Budget).
    d0_fraction_of_vej: Mapping[str, float] = field(default_factory=dict)
    # Pro Periode (nach Wachstum): demand_at_reference_price *= exp(N(0, σ²)); σ im Log-Raum, typ. ~0,3
    demand_at_reference_price_log_noise_std: float = 0.3
    # Optional: pro Periode ε_i *= exp(N(0, σ²)) auf Basis von ``resolved_epsilon``; 0 = keine Schwankung
    epsilon_log_noise_std: float = 0.0
    # Optional: RNG-Seed für reproduzierbare Läufe (None = nicht setzen)
    random_seed: int | None = None
    # Kybernetik der Schattenpreise (Schattenpreisfindung aus Timeline)
    price: PriceConfig = field(default_factory=PriceConfig)
    # Roh-Nachfrage gegen ECU-Obergrenze pro Monat: Σ p·c ≤ ecu_per_year/12 (keine VEJ-Logik im Budget)
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

    def resolved_d0_fraction(self) -> dict[str, float]:
        default_f = 0.45
        return {k: float(self.d0_fraction_of_vej.get(k, default_f)) for k in BOUNDARY_KEYS}


def default_config() -> SimulationConfig:
    return SimulationConfig()
