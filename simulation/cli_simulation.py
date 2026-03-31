"""
CLI: Argumente parsen, Simulation starten, Ergebnisse auf stdout ausgeben.

Die eigentliche Simulationslogik liegt im Modul ``ecu_simulation.simulation.simulation``.
"""

from __future__ import annotations

import argparse

from ecu_simulation.logic.observations import BOUNDARY_KEYS
from ecu_simulation.logic.planetary_constants import ALL_BOUNDARIES, BoundaryConstants
from ecu_simulation.simulation.config import SimulationConfig, default_config
from ecu_simulation.simulation.consumption_budget import ConsumptionBudgetMethod
from ecu_simulation.simulation.simulation import PeriodResult, run_simulation

_GROWTH_ORDER = ", ".join(BOUNDARY_KEYS)


def _parse_comma_floats(s: str, n: int, label: str) -> list[float]:
    """Parst ``n`` durch Komma getrennte Fließkommazahlen (Whitespace erlaubt)."""
    parts = [p.strip() for p in s.split(",") if p.strip() != ""]
    if len(parts) != n:
        raise SystemExit(
            f"{label}: genau {n} Werte erwartet (Reihenfolge: {_GROWTH_ORDER}), "
            f"gefunden: {len(parts)}."
        )
    out: list[float] = []
    for raw in parts:
        try:
            out.append(float(raw))
        except ValueError as e:
            raise SystemExit(f"{label}: keine Zahl: {raw!r}") from e
    return out


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ECU-Terminalsimulation",
        epilog=(
            f"Nachfrage-Wachstum: optional --growth mit drei Faktoren ({_GROWTH_ORDER}); "
            "ohne Angabe bleibt der Faktor pro Grenze 1,0."
        ),
    )
    p.add_argument("--ecu", type=float, default=None, help="EcuJ pro Jahr (Untergrenze Σ p·VEJ)")
    p.add_argument("--periods", type=int, default=20, help="Anzahl Perioden")
    p.add_argument(
        "--growth",
        type=str,
        default=None,
        metavar="LISTE",
        help=(
            f"Komma-getrennte multiplikative Nachfrage-Faktoren pro Periode für {_GROWTH_ORDER} "
            "(drei Zahlen, z. B. 1.02,1,1). Ohne diese Option: Faktor 1,0 je Grenze."
        ),
    )
    p.add_argument(
        "--demand-noise-std",
        "--demand-noise",
        type=float,
        default=None,
        dest="demand_noise_std",
        metavar="σ",
        help=(
            "Std.-Abw. im Log-Raum: demand_at_reference_price *= exp(N(0,σ²)) pro Grenze und Periode "
            "(nach Wachstum). 0 = kein Rauschen. Standard aus Konfiguration (typ. 0,3), wenn nicht gesetzt."
        ),
    )
    p.add_argument(
        "--epsilon-noise-std",
        "--elasticity-noise",
        type=float,
        default=None,
        dest="epsilon_noise_std",
        metavar="σ",
        help=(
            "Std.-Abw. im Log-Raum: ε_i *= exp(N(0,σ²)) pro Grenze und Periode (Basis aus Konfiguration). "
            "0 = keine Schwankung. Standard 0."
        ),
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Zufalls-Seed für reproduzierbare Läufe (optional).",
    )
    p.add_argument(
        "--consumption-budget",
        type=str,
        choices=[m.value for m in ConsumptionBudgetMethod],
        default=None,
        dest="consumption_budget",
        metavar="METHODE",
        help=(
            "ECU-Obergrenze für Σ p·c (kein Hochskalieren): "
            "'scale' = proportionale Drosselung nur wenn Rohkonsum die Grenze übersteigt; "
            "'lagrange' = bei Überschreitung Cobb-Douglas-Aufteilung mit Budget = EcuJ. "
            "Standard: scale (Konfiguration)."
        ),
    )
    return p.parse_args(argv)


def _boundary_vej_d_unit(b: BoundaryConstants) -> str:
    """Kurz-Hinweis zu Einheiten von VEJ und consumption in der Legende."""
    if b.key == "co2":
        return "Mt CO₂ a⁻¹ (hier VEJ und consumption in derselben Einheit)"
    if b.key == "hanpp":
        return "Anteil (0–1), VEJ und consumption dimensionslos"
    if b.key == "nitrogen":
        return "kt N a⁻¹"
    return ""


def print_boundary_tables(results: list[PeriodResult]) -> None:
    """Eine Tabelle pro planetarer Grenze: alle Perioden untereinander."""
    if not results:
        return
    for b in ALL_BOUNDARIES:
        k = b.key
        w = 118
        print(f"\n{'─' * w}")
        print(f"  {b.label_de}  (Schlüssel: {k})")
        print(f"{'─' * w}")
        print(
            f"{'Per':>4}  "
            f"{'p [ECU/Einh]':>14}  "
            f"{'consumption':>14}  "
            f"{'p·c [ECU]':>14}  "
            f"{'demand':>14}  "
            f"{'Δ %':>10}  "
            f"{'VEJ':>14}  "
            f"{'c/VEJ %':>10}"
        )
        print("-" * w)
        for i, r in enumerate(results):
            p = r.prices[k]
            c = r.consumption[k]
            ecu_flow = p * c
            d_ref = r.demand_at_reference_price[k]
            v = r.vej[k]
            if i == 0:
                dd = f"{'—':>10}"
            else:
                dd = f"{_fmt_pct_delta(c, results[i - 1].consumption[k]):>10}"
            pct_vej = (100.0 * c / v) if v > 0 else float("nan")
            pct_str = f"{pct_vej:10.2f}" if pct_vej == pct_vej else "       n/a"
            print(
                f"{r.period:4d}  {p:14.6g}  {c:14.6g}  {ecu_flow:14.6g}  "
                f"{d_ref:14.6g}  {dd}  {v:14.6g}  {pct_str}"
            )
        print(
            "Legende · "
            "p = Schattenpreis (ECU pro Einheit Kontrollvariable); "
            "consumption = modellierter Konsum bei diesem p; "
            "p·c = ECU-Verbrauch an dieser Grenze (Schattenpreis × Konsum); "
            "demand = demand_at_reference_price (Nachfrage-Skalierung bei p_ref, Wachstum/Rauschen); "
            "VEJ = erlaubte Jahresmenge (Obergrenze); "
            "Δ % = prozentuale Änderung von consumption zur Vorperiode; "
            "c/VEJ % = Konsum relativ zur Obergrenze. "
            f"Einheiten: {_boundary_vej_d_unit(b)}"
        )


def print_ecu_accounting_table(results: list[PeriodResult], ecu_start: float) -> None:
    """EcuJ-Obergrenze, tatsächliche Ausgabe Σ p·c, und VEJ-Bündel Σ p·VEJ (Preisrahmen)."""
    w = 100
    print(f"\n{'─' * w}")
    print("  ECU-Menge und Kontenrahmen (alle Grenzen)")
    print(f"{'─' * w}")
    print(
        f"{'Per':>4}  "
        f"{'EcuJ (Deckel)':>14}  "
        f"{'Σ p·c':>14}  "
        f"{'Σ p·VEJ':>14}  "
        f"{'Slack*':>10}  "
        f"{'Ø Auslast.':>10}"
    )
    print("-" * w)
    for r in results:
        slack_vej = r.bundle_ecu - r.ecu_floor
        print(
            f"{r.period:4d}  "
            f"{r.ecu_floor:14.8g}  "
            f"{r.ecu_expenditure:14.8g}  "
            f"{r.bundle_ecu:14.8g}  "
            f"{slack_vej:10.6g}  "
            f"{r.mean_utilization:10.4f}"
        )
    print(
        f"Legende · EcuJ (Deckel) = {ecu_start:g} (konstant). "
        "**Σ p·c** = tatsächlich verbuchte ECU (Summe der Grenztabellen), ≤ EcuJ. "
        "**Σ p·VEJ** = hypothetischer Wert, wenn an jeder Grenze bis VEJ konsumiert würde — "
        "nur für die Schattenpreis-/Bilanzlogik; **nicht** gleich der Ausgabe. "
        "*Slack = Σ p·VEJ − EcuJ (Preisuntergrenze). "
        "Ø Auslastung = Mittel aus min(consumption/VEJ, 1)."
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
    print(f"EcuJ (Ausgaben-Deckel Σ p·c, konstant) = {cfg.ecu_per_year!r}")
    print(
        f"Konsum-Budgetabbildung: {cfg.consumption_budget_method.value} "
        "(Σ p·consumption ≤ EcuJ, keine Aufstockung)"
    )
    print()
    print(
        "Symbole: consumption = modellierter Konsum (Nachfragemenge) · p = Schattenpreis · "
        "p_ref = Referenzpreis · demand_at_reference_price = Skalierung bei p_ref · "
        "VEJ = erlaubte Jahresmenge · ε = Preiselastizität (<0)."
    )
    print(
        "Ausgaben: **Σ p·c ≤ EcuJ** (siehe Spalte Σ p·c in der Übersicht). "
        "Preislogik: **EcuJ ≤ Σ p_i·VEJ_i** (Wert des vollen VEJ-Bündels — kann über der Ausgabe liegen). "
        "Isoelastische Kurve aus demand; Budgetabbildung in der Simulation."
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
    if args.epsilon_noise_std is not None:
        cfg.epsilon_log_noise_std = args.epsilon_noise_std
    if args.seed is not None:
        cfg.random_seed = args.seed
    if args.consumption_budget is not None:
        cfg.consumption_budget_method = ConsumptionBudgetMethod(args.consumption_budget)
    if args.growth is not None:
        vals = _parse_comma_floats(args.growth, len(BOUNDARY_KEYS), "--growth")
        growth = {BOUNDARY_KEYS[i]: vals[i] for i in range(len(BOUNDARY_KEYS))}
    else:
        growth = {k: 1.0 for k in BOUNDARY_KEYS}
    results = run_simulation(cfg, args.periods, demand_growth_per_period=growth)
    print_report(results, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
