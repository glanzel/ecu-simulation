"""
Zeitschritt-Simulation: Gleichgewichts-Schattenpreise, Tauschkurs, Konsum vs. VEJ.

Grenzenwerte als ``dict[str, float]`` (Schlüssel ``BOUNDARY_KEYS``); Beobachtungen als
``ConsumptionInterval`` / ``ConsumptionTimeline``.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable

from ecu_simulation.config import BOUNDARY_KEYS, SimulationConfig
from ecu_simulation.demand import consumption_quantity
from ecu_simulation.exchange import rates_from_prices
from ecu_simulation.observations import (
    DAYS_PER_YEAR,
    ConsumptionInterval,
    ConsumptionTimeline,
)
from ecu_simulation.planetary_constants import ALL_BOUNDARIES, BoundaryConstants
from ecu_simulation.prices import (
    bundle_value,
    consumption_all_below_vej,
    estimate_next_prices_from_timeline,
    enforce_ecu_floor,
    finalize_new_prices_on_last_interval,
    initial_weights_uniform,
    prices_from_weights,
    scale_to_ecu_budget,
)
from ecu_simulation.vej import compute_vej


@dataclass
class PeriodResult:
    period: int
    prices: dict[str, float]
    consumption: dict[str, float]
    vej: dict[str, float]
    bundle_ecu: float
    """Σ p·VEJ — erfüllt EcuJ ≤ bundle_ecu (Slack möglich)."""
    ecu_floor: float
    """Untergrenze EcuJ dieser Periode (verteiltes ECU-Volumen)."""
    mean_utilization: float
    """Mittel aus min(consumption/VEJ, 1) über die drei Grenzen."""
    ecu_per_unit: dict[str, float]
    unit_per_ecu: dict[str, float]
    demand_at_reference_price: dict[str, float]
    consumption_timeline: ConsumptionTimeline
    """Verbrauchsbeobachtungen dieser Periode (Gleichgewichtsschritte)."""


def build_vej_bundle() -> dict[str, float]:
    out: dict[str, float] = {}
    for b in ALL_BOUNDARIES:
        out[b.key] = compute_vej(b.AG, b.VK, b.RZ)
    return out


def _make_consumption_closure(
    demand_at_reference_price: dict[str, float],
    reference_shadow_price: dict[str, float],
    price_elasticity: dict[str, float],
):
    def consumption_at_prices(shadow: dict[str, float]) -> dict[str, float]:
        out: dict[str, float] = {}
        for k in BOUNDARY_KEYS:
            out[k] = consumption_quantity(
                shadow[k],
                demand_at_reference_price[k],
                reference_shadow_price[k],
                price_elasticity[k],
            )
        return out

    return consumption_at_prices


def run_equilibrium_prices(
    vej: dict[str, float],
    ecu_floor: float,
    cfg: SimulationConfig,
    realized_consumption: Callable[[dict[str, float]], dict[str, float]],
    zeitraum_days: float = DAYS_PER_YEAR,
) -> tuple[dict[str, float], dict[str, float], ConsumptionTimeline]:
    """
    Sucht (p, consumption) mit consumption_i ≤ VEJ_i und Σ p_i·VEJ_i ≥ ecu_floor.
    """
    timeline = ConsumptionTimeline()
    step = 0
    p = prices_from_weights(vej, ecu_floor, initial_weights_uniform(len(BOUNDARY_KEYS)))
    p = scale_to_ecu_budget(p, vej, ecu_floor)

    tol = cfg.tolerance
    consumption = realized_consumption(p)
    timeline.append(
        ConsumptionInterval.from_observation(step, zeitraum_days, p, consumption, vej),
    )
    step += 1

    if consumption_all_below_vej(consumption, vej, tol):
        p = enforce_ecu_floor(p, vej, ecu_floor, tol)
        finalize_new_prices_on_last_interval(timeline, p)
        consumption = realized_consumption(p)
        timeline.append(
            ConsumptionInterval.from_observation(step, zeitraum_days, p, consumption, vej),
        )
        return p, consumption, timeline

    for _ in range(cfg.max_price_iterations):
        p_next = estimate_next_prices_from_timeline(timeline, ecu_floor, cfg)
        last_prices = timeline.last.shadow_prices_map()
        unchanged = all(
            abs(p_next[k] - last_prices[k])
            <= tol * max(1.0, abs(last_prices[k]))
            for k in BOUNDARY_KEYS
        )
        consumption = realized_consumption(p_next)
        timeline.append(
            ConsumptionInterval.from_observation(step, zeitraum_days, p_next, consumption, vej),
        )
        step += 1

        if consumption_all_below_vej(consumption, vej, tol):
            p = enforce_ecu_floor(p_next, vej, ecu_floor, tol)
            finalize_new_prices_on_last_interval(timeline, p)
            consumption = realized_consumption(p)
            timeline.append(
                ConsumptionInterval.from_observation(step, zeitraum_days, p, consumption, vej),
            )
            return p, consumption, timeline

        if unchanged:
            break

    last_p = timeline.last.shadow_prices_map()
    p = enforce_ecu_floor(last_p, vej, ecu_floor, tol)
    finalize_new_prices_on_last_interval(timeline, p)
    consumption = realized_consumption(p)
    timeline.append(
        ConsumptionInterval.from_observation(step, zeitraum_days, p, consumption, vej),
    )
    return p, consumption, timeline


def run_period(
    vej: dict[str, float],
    demand_at_reference_price: dict[str, float],
    reference_shadow_price: dict[str, float],
    price_elasticity: dict[str, float],
    cfg: SimulationConfig,
    ecu_floor: float,
) -> tuple[dict[str, float], dict[str, float], float, ConsumptionTimeline]:
    realized_consumption = _make_consumption_closure(
        demand_at_reference_price, reference_shadow_price, price_elasticity
    )
    p, consumption, timeline = run_equilibrium_prices(
        vej, ecu_floor, cfg, realized_consumption, DAYS_PER_YEAR
    )
    bv = bundle_value(p, vej)
    return p, consumption, bv, timeline


def mean_boundary_utilization(consumption: dict[str, float], vej: dict[str, float]) -> float:
    """Durchschnitt der Auslastung pro Grenze (consumption/VEJ, maximal 1)."""
    parts = [
        min(1.0, consumption[k] / vej[k]) if vej[k] > 0 else 0.0
        for k in BOUNDARY_KEYS
    ]
    return sum(parts) / len(parts)


def next_ecu_budget(current: float, mean_u: float, cfg: SimulationConfig) -> float:
    """Steigt mittlere Auslastung → EcuJ senken; fällt sie → erhöhen."""
    factor = 1.0 - cfg.ecu_adjustment_kappa * (mean_u - cfg.utilization_target)
    nxt = current * factor
    return max(cfg.ecu_min, min(cfg.ecu_max, nxt))


def run_simulation(
    cfg: SimulationConfig,
    periods: int,
    demand_growth_per_period: dict[str, float] | None = None,
) -> list[PeriodResult]:
    """
    periods: Anzahl Zeitschritte.
    demand_growth_per_period: multiplikativer Faktor pro Grenze pro Periode (z. B. nur co2 > 1).
    """
    if cfg.random_seed is not None:
        random.seed(cfg.random_seed)

    vej = build_vej_bundle()
    price_elasticity = cfg.resolved_epsilon()
    frac = cfg.resolved_d0_fraction()
    demand_at_reference_price = {k: frac[k] * vej[k] for k in BOUNDARY_KEYS}
    growth = demand_growth_per_period or {k: 1.0 for k in BOUNDARY_KEYS}

    ecu_current = cfg.ecu_per_year
    p_start = prices_from_weights(vej, ecu_current, initial_weights_uniform(len(BOUNDARY_KEYS)))
    p_start = scale_to_ecu_budget(p_start, vej, ecu_current)
    reference_shadow_price = cfg.resolved_p_ref(p_start)

    results: list[PeriodResult] = []
    noise_std = cfg.demand_at_reference_price_log_noise_std
    for t in range(periods):
        demand_at_reference_price = {
            k: demand_at_reference_price[k] * growth[k] for k in BOUNDARY_KEYS
        }
        if noise_std > 0.0:
            for k in BOUNDARY_KEYS:
                demand_at_reference_price[k] *= math.exp(random.gauss(0.0, noise_std))
        ecu_floor = ecu_current
        p, consumption, bv, consumption_timeline = run_period(
            vej,
            demand_at_reference_price,
            reference_shadow_price,
            price_elasticity,
            cfg,
            ecu_floor,
        )
        mean_u = mean_boundary_utilization(consumption, vej)
        xr = rates_from_prices(p)
        results.append(
            PeriodResult(
                period=t + 1,
                prices=p,
                consumption=consumption,
                vej=vej,
                bundle_ecu=bv,
                ecu_floor=ecu_floor,
                mean_utilization=mean_u,
                ecu_per_unit=xr.ecu_per_unit,
                unit_per_ecu=xr.unit_per_ecu,
                demand_at_reference_price=dict(demand_at_reference_price),
                consumption_timeline=consumption_timeline,
            )
        )
        ecu_current = next_ecu_budget(ecu_current, mean_u, cfg)
    return results


def format_table_row(keys: tuple[str, ...], row: dict[str, float], width: int = 12) -> str:
    parts = [f"{row[k]:{width}.6g}" for k in keys]
    return " ".join(parts)


def _boundary_vej_d_unit(b: BoundaryConstants) -> str:
    """Kurz-Hinweis zu Einheiten von VEJ und consumption in der Legende."""
    if b.key == "co2":
        return "Gt CO₂ a⁻¹ (hier VEJ und consumption in derselben Einheit)"
    if b.key == "hanpp":
        return "Anteil (0–1), VEJ und consumption dimensionslos"
    if b.key == "nitrogen":
        return "Tg N a⁻¹"
    return ""


def print_boundary_tables(results: list[PeriodResult]) -> None:
    """Eine Tabelle pro planetarer Grenze: alle Perioden untereinander."""
    if not results:
        return
    for b in ALL_BOUNDARIES:
        k = b.key
        w = 100
        print(f"\n{'─' * w}")
        print(f"  {b.label_de}  (Schlüssel: {k})")
        print(f"{'─' * w}")
        print(
            f"{'Per':>4}  "
            f"{'p [ECU/Einh]':>14}  "
            f"{'consumption':>14}  "
            f"{'demand':>14}  "
            f"{'Δ %':>10}  "
            f"{'VEJ':>14}  "
            f"{'c/VEJ %':>10}"
        )
        print("-" * w)
        for i, r in enumerate(results):
            p = r.prices[k]
            c = r.consumption[k]
            d_ref = r.demand_at_reference_price[k]
            v = r.vej[k]
            if i == 0:
                dd = f"{'—':>10}"
            else:
                dd = f"{_fmt_pct_delta(c, results[i - 1].consumption[k]):>10}"
            pct_vej = (100.0 * c / v) if v > 0 else float("nan")
            pct_str = f"{pct_vej:10.2f}" if pct_vej == pct_vej else "       n/a"
            print(
                f"{r.period:4d}  {p:14.6g}  {c:14.6g}  {d_ref:14.6g}  {dd}  {v:14.6g}  {pct_str}"
            )
        print(
            "Legende · "
            "p = Schattenpreis (ECU pro Einheit Kontrollvariable); "
            "consumption = modellierter Konsum bei diesem p; "
            "demand = demand_at_reference_price (Nachfrage-Skalierung bei p_ref, Wachstum/Rauschen); "
            "VEJ = erlaubte Jahresmenge (Obergrenze); "
            "Δ % = prozentuale Änderung von consumption zur Vorperiode; "
            "c/VEJ % = Konsum relativ zur Obergrenze. "
            f"Einheiten: {_boundary_vej_d_unit(b)}"
        )


def print_ecu_accounting_table(results: list[PeriodResult], ecu_start: float) -> None:
    """Kontenrahmen: EcuJ ≤ Σ p·VEJ; dynamisches EcuJ je nach mittlerer Auslastung."""
    print(f"\n{'─' * 72}")
    print("  ECU-Menge und Kontenrahmen (alle Grenzen)")
    print(f"{'─' * 72}")
    print(
        f"{'Per':>4}  "
        f"{'EcuJ (Untergr.)':>16}  "
        f"{'Σ p·VEJ':>14}  "
        f"{'Slack':>10}  "
        f"{'Ø Auslast.':>10}"
    )
    print("-" * 72)
    for r in results:
        slack = r.bundle_ecu - r.ecu_floor
        print(
            f"{r.period:4d}  "
            f"{r.ecu_floor:16.8g}  "
            f"{r.bundle_ecu:14.8g}  "
            f"{slack:10.6g}  "
            f"{r.mean_utilization:10.4f}"
        )
    print(
        f"Legende · Start-EcuJ (erste Periode Untergrenze) = {ecu_start:g}; "
        "es gilt **EcuJ ≤ Σ p_i·VEJ_i** (Spalte Slack ≥ 0). "
        "Ø Auslastung = Mittel aus min(consumption/VEJ, 1); steigt sie über utilization_target, "
        "wird die nächste Periode weniger EcuJ verteilt (und umgekehrt)."
    )


def _pct_change(new: float, old: float) -> float:
    if old <= 0:
        return float("nan")
    return 100.0 * (new - old) / old


def _fmt_pct_delta(new: float, old: float) -> str:
    """Prozentuale Änderung zur Vorperiode als kurzer String für die Tabelle."""
    d = _pct_change(new, old)
    if d != d:  # NaN
        return "n/a"
    return f"{d:+.2f}"


def print_report(
    results: list[PeriodResult],
    cfg: SimulationConfig,
) -> None:
    keys = BOUNDARY_KEYS
    print("ECU-Terminalsimulation — Schattenpreise und Konsum je planetarer Grenze")
    print(
        f"Start-EcuJ = {cfg.ecu_per_year!r} · Ziel-Auslastung = {cfg.utilization_target!r} · "
        f"κ = {cfg.ecu_adjustment_kappa!r}"
    )
    print()
    print(
        "Symbole: consumption = modellierter Konsum (Nachfragemenge) · p = Schattenpreis · "
        "p_ref = Referenzpreis · demand_at_reference_price = Skalierung bei p_ref · "
        "VEJ = erlaubte Jahresmenge · ε = Preiselastizität (<0)."
    )
    print(
        "Kontenrahmen: **EcuJ ≤ Σ p_i·VEJ_i** (Untergrenze für den ECU-Wert der vollen VEJ); "
        "Slack erlaubt. Isoelastische Kurve: consumption_i = demand_at_reference_price_i·"
        "(p_i/p_ref_i)^ε; Preisfindung aus ConsumptionTimeline, Regler: consumption ≤ VEJ. "
        "EcuJ pro Periode passt sich der mittleren Grenzen-Auslastung an."
    )
    print_boundary_tables(results)
    print_ecu_accounting_table(results, cfg.ecu_per_year)
    print()
    print("Tauschkurs (letzte Periode): ECU pro Einheit / Einheit pro ECU")
    last = results[-1]
    for k in keys:
        print(
            f"  {k}: ecu/unit = {last.ecu_per_unit[k]:.6g}, unit/ecu = {last.unit_per_ecu[k]:.6g}"
        )
