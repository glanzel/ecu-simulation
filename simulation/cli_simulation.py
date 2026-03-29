"""
CLI: Argumente parsen, Simulation starten, Ergebnisse auf stdout ausgeben.

Die eigentliche Simulationslogik liegt im Modul ``ecu_simulation.simulation.simulation``.
"""

from __future__ import annotations

import argparse

from ecu_simulation.logic.observations import BOUNDARY_KEYS
from ecu_simulation.logic.planetary_constants import ALL_BOUNDARIES, BoundaryConstants
from ecu_simulation.simulation.config import SimulationConfig, default_config
from ecu_simulation.simulation.simulation import PeriodResult, run_simulation


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ECU-Terminalsimulation")
    p.add_argument("--ecu", type=float, default=None, help="Start-EcuJ pro Jahr")
    p.add_argument("--periods", type=int, default=20, help="Anzahl Perioden")
    p.add_argument(
        "--growth-co2",
        type=float,
        dest="growth_co2",
        default=1.0,
        help="Multiplikativer Nachfrage-Faktor pro Periode (nur CO₂)",
    )
    p.add_argument(
        "--demand-noise-std",
        type=float,
        default=None,
        metavar="σ",
        help=(
            "Std.-Abw. im Log-Raum für Rauschen auf demand_at_reference_price pro Periode "
            "(nach Wachstum); 0 = aus. Standard aus Konfiguration (typ. 0,3)."
        ),
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Zufalls-Seed für reproduzierbare Läufe (optional).",
    )
    return p.parse_args(argv)


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


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg: SimulationConfig = default_config()
    if args.ecu is not None:
        cfg.ecu_per_year = args.ecu
    if args.demand_noise_std is not None:
        cfg.demand_at_reference_price_log_noise_std = args.demand_noise_std
    if args.seed is not None:
        cfg.random_seed = args.seed
    growth = {k: 1.0 for k in BOUNDARY_KEYS}
    growth["co2"] = args.growth_co2
    results = run_simulation(cfg, args.periods, demand_growth_per_period=growth)
    print_report(results, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
