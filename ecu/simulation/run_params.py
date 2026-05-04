"""
Gemeinsame Laufparameter für CLI und Web (GET): Aufbau von ``SimulationConfig`` und Wachstumsvektor.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from urllib.parse import quote

from ecu.logic.observations import BOUNDARY_KEYS
from ecu.logic.planetary_constants import default_growth_by_key
from ecu.simulation.config import SimulationConfig
from ecu.simulation.consumption_budget import ConsumptionBudgetMethod


def _parse_one_float_token(raw: str) -> float:
    t = raw.strip()
    if t.endswith("%"):
        t = t[:-1].strip()
    return float(t)


def parse_float_list(s: str, n: int, label: str) -> list[float]:
    """Parst ``n`` Zahlen; Trenner: ``|``, ``;`` oder ``,``; optionales Suffix ``%`` pro Wert."""
    s = s.strip()
    if "|" in s:
        parts = [p.strip() for p in s.split("|") if p.strip() != ""]
    elif ";" in s:
        parts = [p.strip() for p in s.split(";") if p.strip() != ""]
    else:
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
            out.append(_parse_one_float_token(raw))
        except ValueError as e:
            raise ValueError(f"{label}: keine Zahl: {raw!r}") from e
    return out


def parse_comma_floats(s: str, n: int, label: str) -> list[float]:
    """Abwärtskompatibel: gleich wie :func:`parse_float_list`."""
    return parse_float_list(s, n, label)


@dataclass
class RunParams:
    """Optionen eines Simulationslaufs (Jahre → Monate intern).

    ``growth``: **Index** je Grenze (ganze Zahlen wie 100, 110, 90): Jahresfaktor = Index/100
    (100 = kein Wachstum, 110 = +10 %, 90 = −10 % **pro Jahr**; pro Zeitschritt ``(Index/100)^(1/steps_per_year)``,
    vgl. ``run_simulation(..., steps_per_year=…)`` — Standard 12 Monate, später z. B. 365 täglich).
    ``start_demand``: Anteil der VEJ in % (Anteil = p/100).
    ``price_max_bundle_scale_pct`` (optional): p in % — Klemme der Σ p·VEJ-Normierung ggü. voriger Periode
    bei hoher Auslastung; 0 = immer exakte Normierung. Standard aus ``PriceConfig``.
    """

    ecu: float | None = None
    periods_years: int = 5
    growth_csv: str | None = None
    start_demand_csv: str | None = None
    demand_noise_std: float | None = None
    epsilon_noise_std: float | None = None
    seed: int | None = None
    consumption_budget: str | None = None
    max_shadow_bundle_scale_pct_per_period: float | None = None

    @classmethod
    def from_argparse(cls, ns: argparse.Namespace) -> RunParams:
        return cls(
            ecu=ns.ecu,
            periods_years=ns.periods,
            growth_csv=ns.growth,
            start_demand_csv=getattr(ns, "start_demand", None),
            demand_noise_std=ns.demand_noise_std,
            epsilon_noise_std=ns.epsilon_noise_std,
            seed=ns.seed,
            consumption_budget=ns.consumption_budget,
            max_shadow_bundle_scale_pct_per_period=getattr(
                ns, "price_max_bundle_scale_pct", None
            ),
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
        if self.start_demand_csv is not None:
            vals = parse_float_list(self.start_demand_csv, len(BOUNDARY_KEYS), "start_demand")
            cfg.start_demand_of_vej = {
                BOUNDARY_KEYS[i]: RunParams._start_demand_percent_to_fraction(vals[i])
                for i in range(len(BOUNDARY_KEYS))
            }
        if self.max_shadow_bundle_scale_pct_per_period is not None:
            cfg.price.max_shadow_bundle_scale_pct_per_period = (
                self.max_shadow_bundle_scale_pct_per_period
            )

    def growth_per_boundary(self) -> dict[str, float]:
        """Multiplikativer Jahresfaktor pro Grenze; Eingabe als Index (100 = Faktor 1)."""
        if self.growth_csv is None:
            return default_growth_by_key()
        vals = parse_float_list(self.growth_csv, len(BOUNDARY_KEYS), "growth")
        return {
            BOUNDARY_KEYS[i]: RunParams._growth_index_to_factor(vals[i]) for i in range(len(BOUNDARY_KEYS))
        }

    @staticmethod
    def _growth_index_to_factor(index: float) -> float:
        """100 = unverändert, 110 = Faktor 1,1, 90 = Faktor 0,9."""
        return index / 100.0

    @staticmethod
    def _start_demand_percent_to_fraction(p: float) -> float:
        return p / 100.0

    @classmethod
    def from_web_query(
        cls,
        *,
        ecu: float | None = None,
        periods: int = 5,
        growth: str | None = None,
        start_demand: str | None = None,
        demand_noise_std: float | None = None,
        epsilon_noise_std: float | None = None,
        seed: int | None = None,
        consumption_budget: str | None = None,
        price_max_bundle_scale_pct: float | None = None,
    ) -> RunParams:
        """Parameter wie bei FastAPI-``Query``-Defaults (fehlende Optionals = Konfig-Default)."""
        return cls(
            ecu=ecu,
            periods_years=periods,
            growth_csv=growth,
            start_demand_csv=start_demand,
            demand_noise_std=demand_noise_std,
            epsilon_noise_std=epsilon_noise_std,
            seed=seed,
            consumption_budget=consumption_budget,
            max_shadow_bundle_scale_pct_per_period=price_max_bundle_scale_pct,
        )

    def to_url_query(self) -> str:
        """GET-Querystring; ``growth`` = Index-Liste, ``start_demand`` = %-Liste; ``|`` ohne ``%2C``."""
        pipe_keys = frozenset({"growth", "start_demand"})

        def enc(k: str, v: str) -> str:
            if k in pipe_keys:
                return quote(v, safe="|")
            return quote(str(v), safe="")

        items: list[tuple[str, str]] = [("periods", str(self.periods_years))]
        if self.ecu is not None:
            items.append(("ecu", str(self.ecu)))
        if self.growth_csv is not None:
            items.append(("growth", self.growth_csv))
        if self.start_demand_csv is not None:
            items.append(("start_demand", self.start_demand_csv))
        if self.demand_noise_std is not None:
            items.append(("demand_noise_std", str(self.demand_noise_std)))
        if self.epsilon_noise_std is not None:
            items.append(("epsilon_noise_std", str(self.epsilon_noise_std)))
        if self.seed is not None:
            items.append(("seed", str(self.seed)))
        if self.consumption_budget is not None:
            items.append(("consumption_budget", self.consumption_budget))
        if self.max_shadow_bundle_scale_pct_per_period is not None:
            items.append(
                (
                    "price_max_bundle_scale_pct",
                    str(self.max_shadow_bundle_scale_pct_per_period),
                )
            )
        return "&".join(f"{k}={enc(k, v)}" for k, v in items)
