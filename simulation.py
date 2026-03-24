"""
Zeitschritt-Simulation: Gleichgewichts-Schattenpreise, Tauschkurs, Nachfrage vs. VEJ.

Eine eventuelle reale Überschreitung planetarer Grenzen wird hier nicht abgebildet:
Die Simulation arbeitet mit den aus AG/VK/RZ abgeleiteten VEJ als Obergrenzen und der
modellierten Nachfrage — nicht mit „aktueller“ globaler Überschreitung als Eingang.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ecu_simulation.config import BOUNDARY_KEYS, SimulationConfig
from ecu_simulation.demand import demand_quantity
from ecu_simulation.exchange import rates_from_prices
from ecu_simulation.observations import (
    DAYS_PER_YEAR,
    ConsumptionTimeline,
    consumption_interval_from_observation,
)
from ecu_simulation.planetary_constants import ALL_BOUNDARIES, BoundaryConstants
from ecu_simulation.prices import (
    bundle_value,
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
    demand: dict[str, float]
    vej: dict[str, float]
    bundle_ecu: float
    """Σ p·VEJ — erfüllt EcuJ ≤ bundle_ecu (Slack möglich)."""
    ecu_floor: float
    """Untergrenze EcuJ dieser Periode (verteiltes ECU-Volumen)."""
    mean_utilization: float
    """Mittel aus min(D/VEJ, 1) über die drei Grenzen."""
    ecu_per_unit: dict[str, float]
    unit_per_ecu: dict[str, float]
    # D_i(p_ref): Skalierung der isoelastischen Kurve (wächst mit Wachstumsfaktoren pro Periode)
    demand_at_reference_price: dict[str, float]
    consumption_timeline: ConsumptionTimeline
    """Verbrauchsbeobachtungen dieser Periode (Gleichgewichtsschritte)."""


def build_vej_map() -> dict[str, float]:
    return {b.key: compute_vej(b.AG, b.VK, b.RZ) for b in ALL_BOUNDARIES}


def _make_demand_closure(
    vej: dict[str, float],
    demand_at_reference_price: dict[str, float],
    reference_shadow_price: dict[str, float],
    price_elasticity: dict[str, float],
):
    def demand_at(prices: dict[str, float]) -> dict[str, float]:
        return {
            k: demand_quantity(
                prices[k],
                demand_at_reference_price[k],
                reference_shadow_price[k],
                price_elasticity[k],
            )
            for k in BOUNDARY_KEYS
        }

    return demand_at


def run_equilibrium_prices(
    vej: dict[str, float],
    ecu_floor: float,
    cfg: SimulationConfig,
    realized_demand: Callable[[dict[str, float]], dict[str, float]],
    zeitraum_days: float = DAYS_PER_YEAR,
) -> tuple[dict[str, float], dict[str, float], ConsumptionTimeline]:
    """
    Sucht (p, u) mit u_i ≤ VEJ_i und Σ p_i·VEJ_i ≥ ecu_floor.

    **Nur hier** wird die modellierte Nachfrage ausgewertet (``realized_demand``).
    Beobachtungen landen in ``ConsumptionTimeline``; die Preislogik liest nur diese Timeline
    und setzt ``new_price`` auf den Records (siehe ``ecu_simulation.prices``).
    """
    timeline: ConsumptionTimeline = []
    step = 0
    p = prices_from_weights(vej, ecu_floor, initial_weights_uniform(len(BOUNDARY_KEYS)))
    p = scale_to_ecu_budget(p, vej, ecu_floor)

    tol = cfg.tolerance
    u = realized_demand(p)
    timeline.append(
        consumption_interval_from_observation(step, zeitraum_days, p, u, vej),
    )
    step += 1

    if all(u[k] <= vej[k] + tol for k in BOUNDARY_KEYS):
        p = enforce_ecu_floor(p, vej, ecu_floor, tol)
        finalize_new_prices_on_last_interval(timeline, p)
        u = realized_demand(p)
        timeline.append(
            consumption_interval_from_observation(step, zeitraum_days, p, u, vej),
        )
        return p, u, timeline

    for _ in range(cfg.max_price_iterations):
        p_next = estimate_next_prices_from_timeline(timeline, vej, ecu_floor, cfg)
        last_prices = {r.control_variable_key: r.price for r in timeline[-1].records}
        unchanged = all(
            abs(p_next[k] - last_prices[k]) <= tol * max(1.0, abs(last_prices[k]))
            for k in BOUNDARY_KEYS
        )
        u = realized_demand(p_next)
        timeline.append(
            consumption_interval_from_observation(step, zeitraum_days, p_next, u, vej),
        )
        step += 1

        if all(u[k] <= vej[k] + tol for k in BOUNDARY_KEYS):
            p = enforce_ecu_floor(p_next, vej, ecu_floor, tol)
            finalize_new_prices_on_last_interval(timeline, p)
            u = realized_demand(p)
            timeline.append(
                consumption_interval_from_observation(step, zeitraum_days, p, u, vej),
            )
            return p, u, timeline

        if unchanged:
            break

    last_p = {r.control_variable_key: r.price for r in timeline[-1].records}
    p = enforce_ecu_floor(last_p, vej, ecu_floor, tol)
    finalize_new_prices_on_last_interval(timeline, p)
    u = realized_demand(p)
    timeline.append(
        consumption_interval_from_observation(step, zeitraum_days, p, u, vej),
    )
    return p, u, timeline


def run_period(
    vej: dict[str, float],
    demand_at_reference_price: dict[str, float],
    reference_shadow_price: dict[str, float],
    price_elasticity: dict[str, float],
    cfg: SimulationConfig,
    ecu_floor: float,
) -> tuple[dict[str, float], dict[str, float], float, ConsumptionTimeline]:
    realized_demand = _make_demand_closure(
        vej, demand_at_reference_price, reference_shadow_price, price_elasticity
    )
    p, u, timeline = run_equilibrium_prices(vej, ecu_floor, cfg, realized_demand, DAYS_PER_YEAR)
    bv = bundle_value(p, vej)
    return p, u, bv, timeline


def mean_boundary_utilization(demand: dict[str, float], vej: dict[str, float]) -> float:
    """Durchschnitt der Auslastung pro Grenze (D/VEJ, maximal 1)."""
    parts = [min(1.0, demand[k] / vej[k]) if vej[k] > 0 else 0.0 for k in BOUNDARY_KEYS]
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
    demand_growth_per_period: optional multiplikativer Faktor pro Grenze pro Periode (z. B. nur co2).
    """
    vej = build_vej_map()
    price_elasticity = cfg.resolved_epsilon()
    frac = cfg.resolved_d0_fraction()
    demand_at_reference_price: dict[str, float] = {
        k: frac[k] * vej[k] for k in BOUNDARY_KEYS
    }
    growth = demand_growth_per_period or {k: 1.0 for k in BOUNDARY_KEYS}

    ecu_current = cfg.ecu_per_year
    # Referenzpreise einmalig aus Start-Skalierung (Start-EcuJ)
    p_start = prices_from_weights(vej, ecu_current, initial_weights_uniform(len(BOUNDARY_KEYS)))
    p_start = scale_to_ecu_budget(p_start, vej, ecu_current)
    reference_shadow_price = cfg.resolved_p_ref(p_start)

    results: list[PeriodResult] = []
    for t in range(periods):
        for k in BOUNDARY_KEYS:
            demand_at_reference_price[k] *= growth.get(k, 1.0)
        ecu_floor = ecu_current
        p, u, bv, consumption_timeline = run_period(
            vej,
            demand_at_reference_price,
            reference_shadow_price,
            price_elasticity,
            cfg,
            ecu_floor,
        )
        mean_u = mean_boundary_utilization(u, vej)
        xr = rates_from_prices(p)
        results.append(
            PeriodResult(
                period=t + 1,
                prices=p,
                demand=u,
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
    """Kurz-Hinweis zu Einheiten von VEJ und D(p) in der Legende."""
    if b.key == "co2":
        return "Gt CO₂ a⁻¹ (hier VEJ und D(p) in derselben Einheit)"
    if b.key == "hanpp":
        return "Anteil (0–1), VEJ und D(p) dimensionslos"
    if b.key == "nitrogen":
        return "Tg N a⁻¹"
    return ""


def print_boundary_tables(results: list[PeriodResult]) -> None:
    """Eine Tabelle pro planetarer Grenze: alle Perioden untereinander."""
    if not results:
        return
    for b in ALL_BOUNDARIES:
        k = b.key
        print(f"\n{'─' * 72}")
        print(f"  {b.label_de}  (Schlüssel: {k})")
        print(f"{'─' * 72}")
        print(
            f"{'Per':>4}  "
            f"{'p [ECU/Einh]':>14}  "
            f"{'D(p)':>14}  "
            f"{'ΔD %':>10}  "
            f"{'VEJ':>14}  "
            f"{'D/VEJ %':>10}"
        )
        print("-" * 72)
        for i, r in enumerate(results):
            p = r.prices[k]
            u = r.demand[k]
            v = r.vej[k]
            if i == 0:
                dd = f"{'—':>10}"
            else:
                dd = f"{_fmt_pct_delta(u, results[i - 1].demand[k]):>10}"
            pct_vej = (100.0 * u / v) if v > 0 else float("nan")
            pct_str = f"{pct_vej:10.2f}" if pct_vej == pct_vej else "       n/a"
            print(
                f"{r.period:4d}  {p:14.6g}  {u:14.6g}  {dd}  {v:14.6g}  {pct_str}"
            )
        print(
            "Legende · "
            "p = Schattenpreis (ECU pro Einheit Kontrollvariable); "
            "D(p) = Modellnachfrage bei diesem p; "
            "VEJ = erlaubte Jahresmenge (Obergrenze); "
            "ΔD % = prozentuale Änderung von D(p) zur Vorperiode; "
            "D/VEJ % = Nachfrage relativ zur Obergrenze. "
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
        "Ø Auslastung = Mittel aus min(D/VEJ, 1); steigt sie über utilization_target, "
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
    print("ECU-Terminalsimulation — Schattenpreise und Nachfrage je planetarer Grenze")
    print(
        f"Start-EcuJ = {cfg.ecu_per_year!r} · Ziel-Auslastung = {cfg.utilization_target!r} · "
        f"κ = {cfg.ecu_adjustment_kappa!r}"
    )
    print()
    print(
        "Symbole: D(p) = modellierte Nachfrage · p = Schattenpreis · p_ref = Referenzpreis · "
        "D(p_ref) = Nachfrage-Skalierung · VEJ = erlaubte Jahresmenge · ε = Preiselastizität (<0)."
    )
    print(
        "Kontenrahmen: **EcuJ ≤ Σ p_i·VEJ_i** (Untergrenze für den ECU-Wert der vollen VEJ); "
        "Slack erlaubt. Modell: D_i(p_i) = D_i(p_ref)·(p_i/p_ref)^ε; Preisfindung aus "
        "ConsumptionTimeline (beobachtete Verbrauchsdaten), Regler: D ≤ VEJ. "
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
