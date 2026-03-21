"""
Zeitschritt-Simulation: Gleichgewichts-Schattenpreise, Tauschkurs, Nachfrage vs. VEJ.

Eine eventuelle reale Überschreitung planetarer Grenzen wird hier nicht abgebildet:
Die Simulation arbeitet mit den aus AG/VK/RZ abgeleiteten VEJ als Obergrenzen und der
modellierten Nachfrage — nicht mit „aktueller“ globaler Überschreitung als Eingang.
"""

from __future__ import annotations

from dataclasses import dataclass

from ecu_sim.config import BOUNDARY_KEYS, SimulationConfig
from ecu_sim.demand import demand_constant_elasticity
from ecu_sim.exchange import rates_from_prices
from ecu_sim.planetary_constants import ALL_BOUNDARIES, BoundaryConstants
from ecu_sim.prices import (
    bundle_value,
    equilibrium_prices,
    initial_weights_uniform,
    prices_from_weights,
    scale_to_ecu_budget,
)
from ecu_sim.vej import compute_vej


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
    d0: dict[str, float]


def build_vej_map() -> dict[str, float]:
    return {b.key: compute_vej(b.AG, b.VK, b.RZ) for b in ALL_BOUNDARIES}


def _make_demand_closure(
    vej: dict[str, float],
    d0: dict[str, float],
    p_ref: dict[str, float],
    epsilon: dict[str, float],
):
    def demand_at(prices: dict[str, float]) -> dict[str, float]:
        return {
            k: demand_constant_elasticity(
                prices[k],
                d0[k],
                p_ref[k],
                epsilon[k],
            )
            for k in BOUNDARY_KEYS
        }

    return demand_at


def run_period(
    vej: dict[str, float],
    d0: dict[str, float],
    p_ref: dict[str, float],
    epsilon: dict[str, float],
    cfg: SimulationConfig,
    ecu_floor: float,
) -> tuple[dict[str, float], dict[str, float], float]:
    demand_at = _make_demand_closure(vej, d0, p_ref, epsilon)
    p, u = equilibrium_prices(vej, ecu_floor, demand_at, cfg)
    bv = bundle_value(p, vej)
    return p, u, bv


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
    eps_map = cfg.resolved_epsilon()
    frac = cfg.resolved_d0_fraction()
    d0: dict[str, float] = {k: frac[k] * vej[k] for k in BOUNDARY_KEYS}
    growth = demand_growth_per_period or {k: 1.0 for k in BOUNDARY_KEYS}

    ecu_current = cfg.ecu_per_year
    # Referenzpreise einmalig aus Start-Skalierung (Start-EcuJ)
    p_start = prices_from_weights(vej, ecu_current, initial_weights_uniform(len(BOUNDARY_KEYS)))
    p_start = scale_to_ecu_budget(p_start, vej, ecu_current)
    p_ref = cfg.resolved_p_ref(p_start)

    results: list[PeriodResult] = []
    for t in range(periods):
        for k in BOUNDARY_KEYS:
            d0[k] *= growth.get(k, 1.0)
        ecu_floor = ecu_current
        p, u, bv = run_period(vej, d0, p_ref, eps_map, cfg, ecu_floor)
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
                d0=dict(d0),
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
        "Kontenrahmen: **EcuJ ≤ Σ p_i·VEJ_i** (Untergrenze für den ECU-Wert der vollen VEJ); "
        "Slack erlaubt. Modell: D_i(p_i) = D0_i·(p_i/p_ref)^ε; Regler: D ≤ VEJ. "
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
