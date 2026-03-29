"""Laufzeit-Konfiguration: EcuJ, Referenzpreise, Elastizitäten, Nachfrage-Basis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ecu_simulation.logic.observations import BOUNDARY_KEYS


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
    # Referenz-Schattenpreis p_ref,i (ECU/Einh.); Fallback: Start-Schattenpreis nach EcuJ-Normierung
    p_ref: Mapping[str, float] = field(default_factory=dict)
    # Konstante Preiselastizität ε_i < 0
    epsilon: Mapping[str, float] = field(default_factory=dict)
    # Anteil f_i: D_i(p_ref) startet als f_i·VEJ_i (isoelastische Skalierung „bei Referenzpreis“)
    d0_fraction_of_vej: Mapping[str, float] = field(default_factory=dict)
    # Pro Periode (nach Wachstum): demand_at_reference_price *= exp(N(0, σ²)); σ in Log-Raum, typ. ~0,3 ≈ 30 % relative Schwankung
    demand_at_reference_price_log_noise_std: float = 0.3
    # Optional: RNG-Seed für reproduzierbare Läufe (None = nicht setzen)
    random_seed: int | None = None
    # Kybernetik (historische Preisfindung: nur beobachtete p, D)
    price_bump: float = 1.08
    max_price_iterations: int = 500
    tolerance: float = 1e-9
    # η̂ = Δln u / Δln p aus zwei Schritten; auf Intervall klemmen (numerisch / Plausibilität)
    price_eta_clip: tuple[float, float] = (-12.0, -0.02)
    # Ein Schritt p_neu/p_alt = (VEJ/D)^(1/η̂) wird auf dieses Intervall begrenzt
    price_step_multiplier_clip: tuple[float, float] = (1.01, 2.5)

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
