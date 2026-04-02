"""
Gemeinsame Laufparameter für CLI und Web (GET): Aufbau von ``SimulationConfig`` und Wachstumsvektor.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from urllib.parse import urlencode

from ecu_simulation.logic.observations import BOUNDARY_KEYS
from ecu_simulation.simulation.config import SimulationConfig
from ecu_simulation.simulation.consumption_budget import ConsumptionBudgetMethod


def parse_comma_floats(s: str, n: int, label: str) -> list[float]:
    """Parst ``n`` durch Komma getrennte Fließkommazahlen (Whitespace erlaubt)."""
    parts = [p.strip() for p in s.split(",") if p.strip() != ""]
    if len(parts) != n:
        order = ", ".join(BOUNDARY_KEYS)
        raise ValueError(
            f"{label}: genau {n} Werte erwartet (Reihenfolge: {order}), "
            f"gefunden: {len(parts)}."
        )
    out: list[float] = []
    for raw in parts:
        try:
            out.append(float(raw))
        except ValueError as e:
            raise ValueError(f"{label}: keine Zahl: {raw!r}") from e
    return out


@dataclass
class RunParams:
    """Optionen eines Simulationslaufs (Jahre → Monate intern)."""

    ecu: float | None = None
    periods_years: int = 5
    growth_csv: str | None = None
    demand_noise_std: float | None = None
    epsilon_noise_std: float | None = None
    seed: int | None = None
    consumption_budget: str | None = None

    @classmethod
    def from_argparse(cls, ns: argparse.Namespace) -> RunParams:
        return cls(
            ecu=ns.ecu,
            periods_years=ns.periods,
            growth_csv=ns.growth,
            demand_noise_std=ns.demand_noise_std,
            epsilon_noise_std=ns.epsilon_noise_std,
            seed=ns.seed,
            consumption_budget=ns.consumption_budget,
        )

    def apply_to_config(self, cfg: SimulationConfig) -> None:
        """Überträgt gesetzte Felder auf ``cfg`` (None = Konfiguration unverändert)."""
        if self.ecu is not None:
            cfg.ecu_per_year = self.ecu
        if self.demand_noise_std is not None:
            cfg.demand_at_reference_price_log_noise_std = self.demand_noise_std
        if self.epsilon_noise_std is not None:
            cfg.epsilon_log_noise_std = self.epsilon_noise_std
        if self.seed is not None:
            cfg.random_seed = self.seed
        if self.consumption_budget is not None:
            cfg.consumption_budget_method = ConsumptionBudgetMethod(self.consumption_budget)

    def growth_per_boundary(self) -> dict[str, float]:
        """Multiplikativer Faktor pro Grenze und Monat (wie ``run_simulation``)."""
        if self.growth_csv is None:
            return {k: 1.0 for k in BOUNDARY_KEYS}
        vals = parse_comma_floats(self.growth_csv, len(BOUNDARY_KEYS), "growth")
        return {BOUNDARY_KEYS[i]: vals[i] for i in range(len(BOUNDARY_KEYS))}

    @classmethod
    def from_web_query(
        cls,
        *,
        ecu: float | None = None,
        periods: int = 5,
        growth: str | None = None,
        demand_noise_std: float | None = None,
        epsilon_noise_std: float | None = None,
        seed: int | None = None,
        consumption_budget: str | None = None,
    ) -> RunParams:
        """Parameter wie bei FastAPI-``Query``-Defaults (fehlende Optionals = Konfig-Default)."""
        return cls(
            ecu=ecu,
            periods_years=periods,
            growth_csv=growth,
            demand_noise_std=demand_noise_std,
            epsilon_noise_std=epsilon_noise_std,
            seed=seed,
            consumption_budget=consumption_budget,
        )

    def to_url_query(self) -> str:
        """GET-Querystring für Links (nur gesetzte optionale Felder zusätzlich zu ``periods``)."""
        parts: list[tuple[str, str]] = [("periods", str(self.periods_years))]
        if self.ecu is not None:
            parts.append(("ecu", str(self.ecu)))
        if self.growth_csv is not None:
            parts.append(("growth", self.growth_csv))
        if self.demand_noise_std is not None:
            parts.append(("demand_noise_std", str(self.demand_noise_std)))
        if self.epsilon_noise_std is not None:
            parts.append(("epsilon_noise_std", str(self.epsilon_noise_std)))
        if self.seed is not None:
            parts.append(("seed", str(self.seed)))
        if self.consumption_budget is not None:
            parts.append(("consumption_budget", self.consumption_budget))
        return urlencode(parts)
