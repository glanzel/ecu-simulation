"""
CLI: Argumente parsen, Simulation starten, Ergebnisse auf stdout ausgeben.

Die eigentliche Simulationslogik liegt im Modul ``ecu_simulation.simulation.simulation``.
"""

from __future__ import annotations

import argparse

from ecu_simulation.logic.observations import BOUNDARY_KEYS, MONTHS_PER_YEAR
from ecu_simulation.logic.planetary_constants import ALL_BOUNDARIES, BoundaryConstants
from ecu_simulation.simulation.config import SimulationConfig, default_config
from ecu_simulation.simulation.consumption_budget import ConsumptionBudgetMethod
from ecu_simulation.simulation.report_aggregates import group_results_by_calendar_year
from ecu_simulation.simulation.run_params import RunParams
from ecu_simulation.simulation.simulation import PeriodResult, run_simulation

_GROWTH_ORDER = ", ".join(BOUNDARY_KEYS)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ECU-Terminalsimulation",
        epilog=(
            f"Listen (--growth, --d0-fraction): drei Werte in Reihenfolge {_GROWTH_ORDER}; "
            "Trenner: | (in URLs ohne %2C), ; oder Komma. "
            "Wachstum: Index 100 = Basis, 110 = +10 Prozent, 90 = −10 Prozent; "
            "f₀: Anteil der VEJ in Prozent (Standard 45 ohne Option)."
        ),
    )
    p.add_argument("--ecu", type=float, default=None, help="EcuJ pro Jahr (Untergrenze Σ p·VEJ)")
    p.add_argument(
        "--periods",
        type=int,
        default=5,
        help=(
            "Anzahl Jahre; die Simulation erzeugt 12 Monatsdatenpunkte pro Jahr "
            f"(VET = VEJ/{MONTHS_PER_YEAR})"
        ),
    )
    p.add_argument(
        "--growth",
        type=str,
        default=None,
        metavar="LISTE",
        help=(
            f"Nachfrage-Index pro Monat ({_GROWTH_ORDER}); Faktor = Index/100, z. B. 102|100|100 (+2 %% auf co2). "
            "100 = unverändert, 110 = +10 %%, 90 = −10 %%. Ohne diese Option: Faktor 1 (wie Index 100)."
        ),
    )
    p.add_argument(
        "--d0-fraction",
        type=str,
        default=None,
        dest="d0_fraction",
        metavar="LISTE",
        help=(
            f"Start-Anteil f_i als Prozent der VEJ bei Referenzpreis ({_GROWTH_ORDER}); "
            "z. B. 42|45|48. Ohne diese Option: 45 %% je Grenze (Konfiguration)."
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
            "(nach Wachstum, je Monat). 0 = kein Rauschen. Standard aus Konfiguration (typ. 0,3), wenn nicht gesetzt."
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
            "Std.-Abw. im Log-Raum: ε_i *= exp(N(0,σ²)) pro Grenze und Monat (Basis aus Konfiguration). "
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


def _boundary_vet_d_unit(b: BoundaryConstants) -> str:
    """Kurz-Hinweis zu Einheiten von VET und consumption in der Legende (monatlich)."""
    if b.key == "co2":
        return "Mt CO₂ Monat⁻¹ (VET und consumption pro Monat)"
    if b.key == "hanpp":
        return "Anteil (0–1), VET und consumption dimensionslos (Monatsfluss)"
    if b.key == "nitrogen":
        return "kt N Monat⁻¹"
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
            f"{'Mon':>4}  "
            f"{'p [ECU/Einh]':>14}  "
            f"{'consumption':>14}  "
            f"{'p·c [ECU]':>14}  "
            f"{'demand':>14}  "
            f"{'Δ %':>10}  "
            f"{'VET':>14}  "
            f"{'c/VET %':>10}"
        )
        print("-" * w)
        for i, r in enumerate(results):
            p = r.prices[k]
            c = r.consumption[k]
            ecu_flow = p * c
            d_ref = r.demand_at_reference_price[k]
            v = r.vet[k]
            if i == 0:
                dd = f"{'—':>10}"
            else:
                dd = f"{_fmt_pct_delta(c, results[i - 1].consumption[k]):>10}"
            pct_vet = (100.0 * c / v) if v > 0 else float("nan")
            pct_str = f"{pct_vet:10.2f}" if pct_vet == pct_vet else "       n/a"
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
            "VET = erlaubte Monatsmenge (VEJ/12); "
            "Δ % = prozentuale Änderung von consumption zum Vormonat; "
            "c/VET % = Konsum relativ zur Monats-Obergrenze. "
            f"Einheiten: {_boundary_vet_d_unit(b)}"
        )


def print_ecu_accounting_table(results: list[PeriodResult], ecu_start: float) -> None:
    """EcuJ (jährlich), monatliche Ausgabe Σ p·c, und jährliches VEJ-Bündel Σ p·VEJ (Preisrahmen)."""
    w = 100
    print(f"\n{'─' * w}")
    print("  ECU-Menge und Kontenrahmen (alle Grenzen)")
    print(f"{'─' * w}")
    print(
        f"{'Mon':>4}  "
        f"{'EcuJ (Jahr)':>14}  "
        f"{'Σ p·c (Mon.)':>14}  "
        f"{'Σ p·VEJ':>14}  "
        f"{'Slack*':>10}  "
        f"{'Ø Auslast.':>10}"
    )
    print("-" * w)
    for r in results:
        slack_vej = r.bundle_ecu - r.ecu_per_year
        print(
            f"{r.period:4d}  "
            f"{r.ecu_per_year:14.8g}  "
            f"{r.ecu_expenditure:14.8g}  "
            f"{r.bundle_ecu:14.8g}  "
            f"{slack_vej:10.6g}  "
            f"{r.mean_utilization:10.4f}"
        )
    print(
        f"Legende · EcuJ (Jahres-Deckel) = {ecu_start:g} (Referenz für Preislogik). "
        "**Σ p·c (Mon.)** = verbuchte ECU im Monat (Summe der Grenztabellen), typ. ≤ EcuJ/12. "
        "**Σ p·VEJ** = hypothetischer Jahreswert zum Monatspreisvektor — "
        "Schattenpreis-/Bilanzlogik; **nicht** gleich der Monatsausgabe. "
        "*Slack = Σ p·VEJ − EcuJ (Preisuntergrenze). "
        "Ø Auslastung = Mittel aus min(consumption/VET, 1)."
    )


def print_yearly_ecu_table(results: list[PeriodResult], ecu_start: float) -> None:
    """Pro Jahr: Summe Σ p·c, repräsentatives Σ p·VEJ (Monatsende), Mittel der Auslastung."""
    by_y = group_results_by_calendar_year(results)
    if not by_y:
        return
    w = 108
    print(f"\n{'─' * w}")
    print("  Jahresübersicht — ECU (Summen über alle Monate des Jahres)")
    print(f"{'─' * w}")
    print(
        f"{'Jahr':>4}  "
        f"{'Monate':>6}  "
        f"{'EcuJ (Jahr)':>14}  "
        f"{'Σ p·c (Jahr)':>14}  "
        f"{'Σ p·VEJ*':>14}  "
        f"{'Slack*':>10}  "
        f"{'Ø Auslast.':>10}"
    )
    print("-" * w)
    for y in sorted(by_y.keys()):
        rows = by_y[y]
        n = len(rows)
        sum_pc = sum(x.ecu_expenditure for x in rows)
        last = rows[-1]
        slack = last.bundle_ecu - last.ecu_per_year
        mean_u = sum(x.mean_utilization for x in rows) / float(n)
        print(
            f"{y:4d}  {n:6d}  "
            f"{last.ecu_per_year:14.8g}  "
            f"{sum_pc:14.8g}  "
            f"{last.bundle_ecu:14.8g}  "
            f"{slack:10.6g}  "
            f"{mean_u:10.4f}"
        )
    print(
        f"Legende · **Σ p·c (Jahr)** = Summe der monatlichen Ausgaben (≤ EcuJ bei 12 Vollmonaten). "
        f"**Σ p·VEJ*** = Wert aus dem **letzten Monat** des Jahres (Preis-/Bilanzrahmen). "
        f"*Slack* = Σ p·VEJ − EcuJ wie in jenem Monat. "
        f"Ist das letzte Jahr kürzer als 12 Monate, ist die Summe entsprechend kleiner."
    )


def print_yearly_boundary_tables(results: list[PeriodResult]) -> None:
    """Pro Jahr und Grenze: Jahressummen Konsum, p·c; Mittelpreis; c/VEJ auf Jahresbasis."""
    by_y = group_results_by_calendar_year(results)
    if not by_y:
        return
    for b in ALL_BOUNDARIES:
        k = b.key
        w = 118
        print(f"\n{'─' * w}")
        print(f"  Jahresübersicht — {b.label_de}  (Schlüssel: {k})")
        print(f"{'─' * w}")
        print(
            f"{'Jahr':>4}  "
            f"{'Mon.':>4}  "
            f"{'Ø p':>14}  "
            f"{'Σ consumption':>14}  "
            f"{'Σ p·c':>14}  "
            f"{'VEJ':>14}  "
            f"{'Σc/VEJ %':>10}  "
            f"{'Δ Jahr %':>10}"
        )
        print("-" * w)
        prev_sum_c: float | None = None
        for y in sorted(by_y.keys()):
            rows = by_y[y]
            n = len(rows)
            sum_c = sum(x.consumption[k] for x in rows)
            sum_pc = sum(x.prices[k] * x.consumption[k] for x in rows)
            mean_p = sum(x.prices[k] for x in rows) / float(n)
            vej = rows[-1].vej[k]
            pct = (100.0 * sum_c / vej) if vej > 0 else float("nan")
            pct_str = f"{pct:10.2f}" if pct == pct else "       n/a"
            if prev_sum_c is None:
                dd = f"{'—':>10}"
            else:
                dd = f"{_fmt_pct_delta(sum_c, prev_sum_c):>10}"
            prev_sum_c = sum_c
            print(
                f"{y:4d}  {n:4d}  {mean_p:14.6g}  {sum_c:14.6g}  {sum_pc:14.6g}  "
                f"{vej:14.6g}  {pct_str}  {dd}"
            )
        print(
            "Legende · Mon. = Anzahl Monate (12 oder weniger im letzten Jahr); "
            "Ø p = Mittel der Monatspreise; Σ consumption = Summe der Monatskonsume; "
            "VEJ = Jahres-Obergrenze; Σc/VEJ % = Σ consumption relativ zu VEJ; "
            "Δ Jahr % = Änderung der Jahressumme Σ consumption zum Vorjahr. "
            f"Einheiten: {_boundary_vej_d_unit(b)}"
        )


def _boundary_vej_d_unit(b: BoundaryConstants) -> str:
    """Jahresübersicht: VEJ und Summe der Monatskonsume (jährliche Einheiten)."""
    if b.key == "co2":
        return "Mt CO₂ a⁻¹ (Σconsumption = Jahresmenge; VEJ = Jahresgrenze)"
    if b.key == "hanpp":
        return "Anteil (0–1), VEJ und Σ consumption dimensionslos (Jahresfluss)"
    if b.key == "nitrogen":
        return "kt N a⁻¹"
    return ""


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
    *,
    simulation_years: int,
) -> None:
    keys = BOUNDARY_KEYS
    n_mon = len(results)
    print("ECU-Terminalsimulation — Schattenpreise und Konsum je planetarer Grenze (monatlich)")
    print(
        f"Lauf: {simulation_years} Jahr(e) = {n_mon} Monat(e) "
        f"(12 Datenpunkte pro Jahr; --periods = Jahre)"
    )
    print(f"EcuJ (Jahres-Referenz; Ausgaben-Deckel pro Monat: EcuJ/12) = {cfg.ecu_per_year!r}")
    print(
        f"Konsum-Budgetabbildung: {cfg.consumption_budget_method.value} "
        "(Σ p·consumption ≤ EcuJ/12 pro Monat, keine Aufstockung)"
    )
    print()
    print(
        "Symbole: consumption = modellierter Konsum (Nachfragemenge) · p = Schattenpreis · "
        "p_ref = Referenzpreis · demand_at_reference_price = Skalierung bei p_ref · "
        "VET = erlaubte Monatsmenge (VEJ/12) · ε = Preiselastizität (<0)."
    )
    print(
        "Ausgaben pro Monat: **Σ p·c ≤ EcuJ/12** (siehe Spalte Σ p·c in der Übersicht). "
        "Preislogik (jährlich): **EcuJ ≤ Σ p_i·VEJ_i** (volles VEJ-Bündel — kann über der Monatsausgabe liegen). "
        "Isoelastische Kurve aus demand; Budgetabbildung in der Simulation."
    )
    print_yearly_ecu_table(results, cfg.ecu_per_year)
    print_yearly_boundary_tables(results)
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
    params = RunParams.from_argparse(args)
    params.apply_to_config(cfg)
    try:
        growth = params.growth_per_boundary()
    except ValueError as e:
        raise SystemExit(str(e)) from e
    months = params.periods_years * MONTHS_PER_YEAR
    results = run_simulation(cfg, months, demand_growth_per_period=growth)
    print_report(results, cfg, simulation_years=params.periods_years)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
