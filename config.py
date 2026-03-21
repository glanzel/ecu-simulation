"""Laufzeit-Konfiguration: EcuJ, Referenzpreise, Elastizitäten, Nachfrage-Basis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

# Reihenfolge der Grenzen (Schlüssel)
BOUNDARY_KEYS: tuple[str, ...] = ("co2", "hanpp", "nitrogen")


@dataclass
class SimulationConfig:
    """Start-EcuJ, dynamische Anpassung, Nachfrageparameter."""

    # Startwert für das verteilte ECU-Jahresvolumen (Untergrenze Σ p·VEJ wird daran gemessen)
    ecu_per_year: float = 1.0
    # Mittlere Auslastung D/VEJ (je Grenze auf 1.0 gedeckelt): Sollwert — darüber wird EcuJ reduziert, darunter erhöht
    utilization_target: float = 0.5
    # Empfindlichkeit: ecu_neu = ecu * (1 - kappa * (mittlere_Auslastung - utilization_target))
    ecu_adjustment_kappa: float = 0.25
    ecu_min: float = 0.01
    ecu_max: float = 1_000_000.0
    # Referenzpreis p_ref_i (ECU pro Einheit); typisch = Start-Schattenpreis nach Normierung
    p_ref: Mapping[str, float] = field(default_factory=dict)
    # Konstante Preiselastizität ε_i < 0
    epsilon: Mapping[str, float] = field(default_factory=dict)
    # Skalierung der Basisnachfrage D0_i relativ zu VEJ_i (0 < factor < 1 empfohlen)
    d0_fraction_of_vej: Mapping[str, float] = field(default_factory=dict)
    # Kybernetik
    price_bump: float = 1.08
    max_price_iterations: int = 500
    tolerance: float = 1e-9

    def resolved_p_ref(self, initial_prices: Mapping[str, float]) -> dict[str, float]:
        """p_ref: explizit oder Fallback auf initial normierte Schattenpreise."""
        out = {k: initial_prices[k] for k in BOUNDARY_KEYS}
        for k in BOUNDARY_KEYS:
            if k in self.p_ref and self.p_ref[k] > 0:
                out[k] = self.p_ref[k]
        return out

    def resolved_epsilon(self) -> dict[str, float]:
        default_eps = -0.4
        return {k: float(self.epsilon.get(k, default_eps)) for k in BOUNDARY_KEYS}

    def resolved_d0_fraction(self) -> dict[str, float]:
        default_f = 0.45
        return {k: float(self.d0_fraction_of_vej.get(k, default_f)) for k in BOUNDARY_KEYS}


def default_config() -> SimulationConfig:
    return SimulationConfig()
