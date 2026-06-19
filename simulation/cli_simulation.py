"""
CLI: Argumente parsen, Simulation starten, Ergebnisse auf stdout ausgeben.

Die eigentliche Simulationslogik liegt im Modul ``simulation.simulation``.
"""

from __future__ import annotations

import argparse

from logic.observations import BOUNDARY_KEYS, MONTHS_PER_YEAR
from logic.planetary_constants import ALL_BOUNDARIES, BoundaryConstants
from simulation.config import SimulationConfig, default_config
from simulation.consumption_budget import ConsumptionBudgetMethod
from simulation.report_aggregates import (
    group_results_by_calendar_year,
    warmup_diagnostic_table_rows,
    WARMUP_DIAG_TABLE_HEADER,
)
from simulation.run_params import RunParams
from simulation.simulation import PeriodResult, run_simulation

_GROWTH_ORDER = ", ".join(BOUNDARY_KEYS)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="ECU-Terminalsimulation",
        epilog=(
            f"Listen (--growth, --start-demand): je {len(BOUNDARY_KEYS)} Werte in Reihenfolge {_GROWTH_ORDER}; "
            "Trenner: | (in URLs ohne %2C), ; oder Komma. "
            "Wachstum: Index 100 = Basis, 110 = +10 Prozent pro Jahr, 90 = −10 Prozent pro Jahr; "
            "ohne --growth: Jahresfaktoren aus planetary_constants (literaturbasierte Defaults). "
            "start-demand: Anteil der VEJ in Prozent; ohne Option: Defaults je Grenze."
        ),
    )
    p.add_argument(
        "--ecu",
        "--ecumenge-ziel-j",
        type=float,
        default=None,
        dest="ecumenge_ziel_J",
        help="ecumenge_ziel_J: langfristiges Jahresziel (Σ p·VEJ-Ziel)",
    )
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
            f"Nachfrage-Index pro Jahr ({_GROWTH_ORDER}); je {len(BOUNDARY_KEYS)} Werte; "
            f"Jahresfaktor = Index/100, pro Zeitschritt (Index/100)^(1/steps_per_year) "
            f"(steps_per_year={MONTHS_PER_YEAR} Monate/Jahr). "
            "100 = unverändert, 110 = +10 %%, 90 = −10 %%. "
            "Ohne diese Option: ``growth`` aus planetary_constants je Grenze."
        ),
    )
    p.add_argument(
        "--start-demand",
        type=str,
        default=None,
        dest="start_demand",
        metavar="LISTE",
        help=(
            f"Start-Nachfrage als Prozent der VEJ bei Referenzpreis ({_GROWTH_ORDER}); "
            f"z. B. neun Werte. Ohne diese Option: ``start_demand`` aus planetary_constants je Grenze."
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
            "Std.-Abw. σ im Log-Raum: demand_at_reference_price *= exp(Z), Z~N(0,σ), pro Grenze und Monat "
            "(nach Wachstum). 0 = kein Rauschen. Standard aus Konfiguration (ln(1,01) ≈ 1 %-Skala bei ±1σ), wenn nicht gesetzt."
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
            "Std.-Abw. σ im Log-Raum: ε_i *= exp(Z), Z~N(0,σ), pro Grenze und Monat (Basis aus Konfiguration). "
            "0 = keine Schwankung. Standard wie Nachfrage-Rauschen (ln(1,01)), wenn nicht gesetzt."
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
            "'lagrange' = bei Überschreitung Konsum als EUKLID-Nächstlage zu Roh-Nachfrage unter Budget ecumenge_T "
            "(nicht mehr Cobb-Douglas-Gewichte). "
            "Standard: scale (Konfiguration)."
        ),
    )
    p.add_argument(
        "--price-max-bundle-scale-pct",
        type=float,
        default=None,
        dest="price_max_bundle_scale_pct",
        metavar="PCT",
        help=(
            "Obergrenze p in % (max_shadow_bundle_scale_pct_per_period): weicher ECU-Ratchet, "
            "harter Σ p·VEJ-Ziel-Pfad, Rohpreis-Stufen — siehe PriceConfig. 0 = exakte Normierung."
        ),
    )
    p.add_argument(
        "--price-elasticity-warmup-months",
        type=int,
        default=None,
        dest="price_elasticity_warmup_months",
        metavar="N",
        help=(
            "Ab N abgeschlossenen Beobachtungsmonaten: OLS-Preiselastizität in den Rohpreisen "
            "(N ist zugleich die Mindestzahl gültiger Historienpunkte); davor nur Bump + weiche Staffel. "
            "Standard: 5 (PriceConfig)."
        ),
    )
    return p.parse_args(argv)


def _boundary_vet_d_unit(b: BoundaryConstants) -> str:
    """Kurz-Hinweis zu Einheiten von VET-Ziel und VEJ-Ist in der Legende (monatlich)."""
    return f"{b.consumption_unit_monthly} (VET-Ziel und VEJ-Ist pro Monat)"


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
            f"{'VEJ-Ist':>14}  "
            f"{'p·VEJ-Ist':>14}  "
            f"{'demand':>14}  "
            f"{'Δ %':>10}  "
            f"{'VET-Ziel':>14}  "
            f"{'Ist/VET-Ziel %':>14}"
        )
        print("-" * w)
        for i, r in enumerate(results):
            p = r.prices[k]
            c = r.vej_ist[k]
            ecu_flow = p * c
            d_ref = r.demand_at_reference_price[k]
            v = r.vet_ziel[k]
            if i == 0:
                dd = f"{'—':>10}"
            else:
                dd = f"{_fmt_pct_delta(c, results[i - 1].vej_ist[k]):>10}"
            pct_vet = (100.0 * c / v) if v > 0 else float("nan")
            pct_str = f"{pct_vet:10.2f}" if pct_vet == pct_vet else "       n/a"
            print(
                f"{r.period:4d}  {p:14.6g}  {c:14.6g}  {ecu_flow:14.6g}  "
                f"{d_ref:14.6g}  {dd}  {v:14.6g}  {pct_str}"
            )
        print(
            "Legende · "
            "p = Schattenpreis (ECU pro Einheit Kontrollvariable); "
            "VEJ-Ist = modellierter Monatsverbrauch bei diesem p; "
            "p·VEJ-Ist = ECU-Verbrauch an dieser Grenze; "
            "demand = demand_at_reference_price (Nachfrage-Skalierung bei p_ref, Wachstum/Rauschen); "
            "VET-Ziel = Monats-Obergrenze (VEJ-Ziel/12); "
            "Δ % = Änderung von VEJ-Ist zum Vormonat; "
            "Ist/VET-Ziel % = VEJ-Ist relativ zur Monats-Obergrenze. "
            f"Einheiten: {_boundary_vet_d_unit(b)}"
        )


def print_ecu_accounting_table(results: list[PeriodResult], ecu_start: float) -> None:
    """ECU-Jahresgrößen (ecumenge_*), monatliche Ausgabe ecu_ist_T, und Kontenrahmen Σ p·VEJ-Ziel."""
    w = 118
    print(f"\n{'─' * w}")
    print("  ECU-Menge und Kontenrahmen (alle Grenzen)")
    print(f"{'─' * w}")
    print(
        f"{'Mon':>4}  "
        f"{'ecumenge_ziel_J':>15}  "
        f"{'ecumenge_J':>15}  "
        f"{'ecumenge_T':>12}  "
        f"{'ecu_ist_T':>14}  "
        f"{'Σ p·VEJ-Ziel':>14}  "
        f"{'Slack*':>10}  "
        f"{'Ø Auslast.':>10}"
    )
    print("-" * w)
    for r in results:
        slack_vej = r.bundle_ecu - r.ecumenge_ziel_J
        print(
            f"{r.period:4d}  "
            f"{r.ecumenge_ziel_J:14.8g}  "
            f"{r.ecumenge_J:14.8g}  "
            f"{r.ecumenge_T:12.6g}  "
            f"{r.ecu_ist_T:14.8g}  "
            f"{r.bundle_ecu:14.8g}  "
            f"{slack_vej:10.6g}  "
            f"{r.mean_utilization:10.4f}"
        )
    print(
        f"Legende · **ecumenge_ziel_J** = konfiguriertes Jahresbudget (Preisnormierung Σ p·VEJ-Ziel). "
        "**ecumenge_J*** = simulierte wirksame Jahres-ECU-Menge am **Simulationsstart** (bei hoher Start-Auslastung ≥ Ziel). "
        "**ecumenge_T** = im Monat simuliert ausgegebene ECU-Menge (Obergrenze für Σ p·VEJ-Ist). "
        "**ecu_ist_T** = verbuchte ECU im Monat (Σ p·VEJ-Ist). "
        "**Σ p·VEJ-Ziel** = hypothetischer Jahreswert zum Monatspreisvektor — "
        "Schattenpreis-/Bilanzlogik; **nicht** gleich der Monatsausgabe. "
        "*Slack = Σ p·VEJ-Ziel − ecumenge_ziel_J (nach Preisnormierung ~0, Rundung). "
        "Ø Auslastung = Mittel aus VEJ-Ist / VET-Ziel je Grenze (Verhältnis, kann > 1 bei Grenzüberschreitung)."
    )


def print_yearly_ecu_table(results: list[PeriodResult], ecu_start: float) -> None:
    """Pro Jahr: Summe Σ p·c, repräsentatives Σ p·VEJ-Ziel (Monatsende), Mittel der Auslastung."""
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
        f"{'ecumenge_ziel_J':>15}  "
        f"{'Σ ecu_ist_T (J)':>18}  "
        f"{'Σ p·VEJ-Ziel*':>14}  "
        f"{'Slack*':>10}  "
        f"{'Ø Auslast.':>10}"
    )
    print("-" * w)
    for y in sorted(by_y.keys()):
        rows = by_y[y]
        n = len(rows)
        sum_pc = sum(x.ecu_ist_T for x in rows)
        last = rows[-1]
        slack = last.bundle_ecu - last.ecumenge_ziel_J
        mean_u = sum(x.mean_utilization for x in rows) / float(n)
        print(
            f"{y:4d}  {n:6d}  "
            f"{last.ecumenge_ziel_J:14.8g}  "
            f"{sum_pc:14.8g}  "
            f"{last.bundle_ecu:14.8g}  "
            f"{slack:10.6g}  "
            f"{mean_u:10.4f}"
        )
    print(
        f"Legende · **Σ ecu_ist_T (J)** = Summe der monatlichen Ist-ECU (≤ ecumenge_ziel_J bei 12 Monaten pro Jahr). "
        f"**Σ p·VEJ-Ziel*** = Wert aus dem **letzten Monat** des Jahres (Preis-/Bilanzrahmen). "
        f"*Slack* = Σ p·VEJ-Ziel − ecumenge_ziel_J (letzter Monat; nach Normierung ~0)."
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
            f"{'Σ VEJ-Ist':>14}  "
            f"{'Σ p·VEJ-Ist':>14}  "
            f"{'VEJ-Ziel':>14}  "
            f"{'Σ Ist/Ziel %':>14}  "
            f"{'Δ Jahr %':>10}"
        )
        print("-" * w)
        prev_sum_c: float | None = None
        for y in sorted(by_y.keys()):
            rows = by_y[y]
            n = len(rows)
            sum_c = sum(x.vej_ist[k] for x in rows)
            sum_pc = sum(x.prices[k] * x.vej_ist[k] for x in rows)
            mean_p = sum(x.prices[k] for x in rows) / float(n)
            vej_ziel = rows[-1].vej_ziel[k]
            pct = (100.0 * sum_c / vej_ziel) if vej_ziel > 0 else float("nan")
            pct_str = f"{pct:10.2f}" if pct == pct else "       n/a"
            if prev_sum_c is None:
                dd = f"{'—':>10}"
            else:
                dd = f"{_fmt_pct_delta(sum_c, prev_sum_c):>10}"
            prev_sum_c = sum_c
            print(
                f"{y:4d}  {n:4d}  {mean_p:14.6g}  {sum_c:14.6g}  {sum_pc:14.6g}  "
                f"{vej_ziel:14.6g}  {pct_str}  {dd}"
            )
        print(
            "Legende · Mon. = Anzahl Monate (12 oder weniger im letzten Jahr); "
            "Ø p = Mittel der Monatspreise; Σ VEJ-Ist = Summe der monatlichen Ist-Werte; "
            "VEJ-Ziel = Jahres-Obergrenze; Σ Ist/Ziel % = Summe VEJ-Ist relativ zu VEJ-Ziel; "
            "Δ Jahr % = Änderung der Jahressumme Σ VEJ-Ist zum Vorjahr. "
            f"Einheiten: {_boundary_vej_d_unit(b)}"
        )


def _boundary_vej_d_unit(b: BoundaryConstants) -> str:
    """Jahresübersicht: VEJ und Summe der Monatskonsume (jährliche Einheiten)."""
    u = b.consumption_unit_monthly.replace("Monat⁻¹", "a⁻¹")
    return f"{u} (Σ VEJ-Ist = Jahressumme Monatswerte; VEJ-Ziel = Jahresgrenze)"


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


def print_warmup_diagnostic_table(results: list[PeriodResult]) -> None:
    wrows = warmup_diagnostic_table_rows(results)
    if not wrows:
        return
    w = 78
    print(f"\n{'─' * w}")
    print("  Warmup — Diagnose Σ p·VET-Ziel vs. ecumenge_ziel_sim_J/12 (ohne Σ p·VEJ-Ziel-Normierung)")
    print(f"{'─' * w}")
    colw = (14, 16, 16, 14, 14)
    print(" ".join(f"{h:>{colw[i]}}" for i, h in enumerate(WARMUP_DIAG_TABLE_HEADER)))
    print("-" * w)
    for row in wrows:
        print(" ".join(f"{c:>{colw[i]}}" for i, c in enumerate(row)))
    print(
        "Legende: nur Monate mit Warmup-Preispfad (erste N Beobachtungen). "
        "Δ Monat = Σ p·VET-Ziel − ecumenge_ziel_sim_J/12; Δ Jahr = 12·Δ Monat."
    )


def print_monthly_price_sums(results: list[PeriodResult]) -> None:
    """
    Monatsübersicht: Σ p·c, Σ p, Δ, Mittel der Auslastung (wie ``PeriodResult.mean_utilization``).
    """
    if not results:
        return
    w = 94
    print(f"\n{'─' * w}")
    print("  Monatsübersicht (Σ p·VEJ-Ist, Auslastung)")
    print(f"{'─' * w}")
    print(
        f"{'Mon':>4}  "
        f"{'Σ p·VEJ-Ist':>16}  "
        f"{'Σ p':>16}  "
        f"{'Δ Σp·VEJ-Ist %':>12}  "
        f"{'Ø Auslast.':>10}"
    )
    print("-" * w)
    prev_pc: float | None = None
    for r in results:
        sum_p = sum(r.prices[k] for k in BOUNDARY_KEYS)
        pc = r.ecu_ist_T
        if prev_pc is None:
            dstr = "—"
        else:
            d = _pct_change(pc, prev_pc)
            dstr = f"{d:+.4f}" if d == d else "n/a"
        print(
            f"{r.period:4d}  "
            f"{pc:16.8g}  "
            f"{sum_p:16.8g}  "
            f"{dstr:>12}  "
            f"{r.mean_utilization:10.4f}"
        )
        prev_pc = pc
    print(
        "Legende: Σ p·VEJ-Ist = Σ_i p_i·vej_ist_i (monatlich verbuchte ECU). "
        "Σ p = Summe der Schattenpreise über alle Grenzen. Δ = Änderung von Σ p·VEJ-Ist zum Vormonat (%). "
        "Ø Auslast. = Mittel aus VEJ-Ist / VET-Ziel je Grenze (kann > 1)."
    )


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
    print(f"ecumenge_ziel_J (Jahres-Referenz; Preisnormierung Σ p·VEJ-Ziel) = {cfg.ecumenge_ziel_J!r}")
    print(
        f"Konsum-Budgetabbildung: {cfg.consumption_budget_method.value} "
        "(Σ p·VEJ-Ist ≤ ecumenge_T: erster Monat aus ecumenge_J/12, sonst Ziel/12 bzw. weicher Pfad)"
    )
    print()
    print(
        "Symbole: VEJ-Ist = modellierter Monatsverbrauch · p = Schattenpreis · "
        "p_ref = Referenzpreis · demand_at_reference_price = Skalierung bei p_ref · "
        "VET-Ziel = Monats-Obergrenze (VEJ-Ziel/12) · ε = Preiselastizität (<0)."
    )
    print(
        "Ausgaben pro Monat: **Σ p·VEJ-Ist ≤ ecumenge_T** (siehe Tabelle Spalten ecumenge_T und ecu_ist_T). "
        "Preislogik (jährlich): **ecumenge_ziel_J ≤ Σ p_i·vej_ziel_i** (volles Ziel-Bündel — kann über der Monatsausgabe liegen). "
        "Isoelastische Kurve aus demand; Budgetabbildung in der Simulation."
    )
    print_monthly_price_sums(results)
    print_warmup_diagnostic_table(results)
    print_yearly_ecu_table(results, cfg.ecumenge_ziel_J)
    print_yearly_boundary_tables(results)
    print_boundary_tables(results)
    print_ecu_accounting_table(results, cfg.ecumenge_ziel_J)
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
    results = run_simulation(cfg, months, demand_growth_per_year=growth)
    print_report(results, cfg, simulation_years=params.periods_years)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
