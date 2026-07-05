"""
Aggregation von ``PeriodResult``-Listen für Jahres-/Grenz-Auswertungen (CLI und Web).
"""

from __future__ import annotations

from dataclasses import dataclass

from logic.observations import MONTHS_PER_YEAR
from simulation.simulation import PeriodResult

WARMUP_DIAG_TABLE_HEADER: list[str] = [
    "Mon",
    "Σ ecu_preis·BudgetT-Ziel (Mon.)",
    "ecumenge_ziel_sim/12",
    "Δ Monat",
    "Δ Jahr",
]


def group_results_by_calendar_year(
    results: list[PeriodResult],
) -> dict[int, list[PeriodResult]]:
    """Gruppiert Monatszeilen nach Kalenderjahr (Jahr 1 = Monate 1–12, usw.)."""
    out: dict[int, list[PeriodResult]] = {}
    for r in results:
        y = (r.period - 1) // MONTHS_PER_YEAR + 1
        if y not in out:
            out[y] = []
        out[y].append(r)
    for rows in out.values():
        rows.sort(key=lambda x: x.period)
    return out


@dataclass
class YearlyEcuSummary:
    """Pro Kalenderjahr über alle Grenzen: verbuchte ECU und Kontenrahmen (wie CLI ``print_yearly_ecu_table``)."""

    year_index: int
    n_months: int
    ecumenge_ziel: float
    sum_ecu_ist_J: float
    ecumenge_kontenrahmen: float
    slack_vej: float
    gesamtauslastung: float


@dataclass
class BoundaryTotalSummary:
    """Gesamtlauf über alle Monate für eine Grenze."""

    boundary_key: str
    sum_nutzung_T: float
    sum_demand_ref: float
    sum_pc: float
    budget_J: float
    pct_nutzung_T_jahr_vs_budget_J: float


@dataclass
class BoundaryYearSummary:
    """Ein Kalenderjahr für eine Grenze (wie CLI-Jahresübersicht)."""

    year_index: int
    n_months: int
    mean_price: float
    sum_nutzung_T: float
    sum_demand_ref: float
    sum_pc: float
    budget_J: float
    pct_nutzung_T_jahr_vs_budget_J: float


def yearly_ecu_summaries(results: list[PeriodResult]) -> list[YearlyEcuSummary]:
    """Jährliche Summen Σ p·c (verbuchte ECU) und Rahmengrößen — alle Grenzen zusammen."""
    by_y = group_results_by_calendar_year(results)
    out: list[YearlyEcuSummary] = []
    for y in sorted(by_y.keys()):
        mrows = by_y[y]
        n = len(mrows)
        sum_pc = sum(x.ecu_ist_T for x in mrows)
        last = mrows[-1]
        slack = last.ecumenge_kontenrahmen - last.ecumenge_ziel
        gesamtauslastung = sum(x.gesamtauslastung for x in mrows) / float(n)
        out.append(
            YearlyEcuSummary(
                year_index=y,
                n_months=n,
                ecumenge_ziel=last.ecumenge_ziel,
                sum_ecu_ist_J=sum_pc,
                ecumenge_kontenrahmen=last.ecumenge_kontenrahmen,
                slack_vej=slack,
                gesamtauslastung=gesamtauslastung,
            )
        )
    return out


def boundary_total_summary(results: list[PeriodResult], boundary_key: str) -> BoundaryTotalSummary:
    """Summen über den gesamten Lauf; BudgetJ aus letztem Monat (konstant)."""
    if not results:
        return BoundaryTotalSummary(
            boundary_key=boundary_key,
            sum_nutzung_T=0.0,
            sum_demand_ref=0.0,
            sum_pc=0.0,
            budget_J=0.0,
            pct_nutzung_T_jahr_vs_budget_J=float("nan"),
        )
    sum_c = sum(r.nutzung_T[boundary_key] for r in results)
    sum_d = sum(r.demand_at_reference_price[boundary_key] for r in results)
    sum_pc = sum(r.prices[boundary_key] * r.nutzung_T[boundary_key] for r in results)
    budget_J = results[-1].budget_J[boundary_key]
    pct = (100.0 * sum_c / budget_J) if budget_J > 0 else float("nan")
    return BoundaryTotalSummary(
        boundary_key=boundary_key,
        sum_nutzung_T=sum_c,
        sum_demand_ref=sum_d,
        sum_pc=sum_pc,
        budget_J=budget_J,
        pct_nutzung_T_jahr_vs_budget_J=pct,
    )


def boundary_year_summaries(results: list[PeriodResult], boundary_key: str) -> list[BoundaryYearSummary]:
    """Sortierte Liste je Kalenderjahr."""
    by_y = group_results_by_calendar_year(results)
    rows: list[BoundaryYearSummary] = []
    for y in sorted(by_y.keys()):
        mrows = by_y[y]
        n = len(mrows)
        sum_c = sum(x.nutzung_T[boundary_key] for x in mrows)
        sum_d = sum(x.demand_at_reference_price[boundary_key] for x in mrows)
        sum_pc = sum(x.prices[boundary_key] * x.nutzung_T[boundary_key] for x in mrows)
        mean_p = sum(x.prices[boundary_key] for x in mrows) / float(n)
        budget_J = mrows[-1].budget_J[boundary_key]
        pct = (100.0 * sum_c / budget_J) if budget_J > 0 else float("nan")
        rows.append(
            BoundaryYearSummary(
                year_index=y,
                n_months=n,
                mean_price=mean_p,
                sum_nutzung_T=sum_c,
                sum_demand_ref=sum_d,
                sum_pc=sum_pc,
                budget_J=budget_J,
                pct_nutzung_T_jahr_vs_budget_J=pct,
            )
        )
    return rows


def months_for_calendar_year(
    results: list[PeriodResult],
    year_index: int,
) -> list[PeriodResult]:
    """Alle Monatszeilen eines Kalenderjahres."""
    by_y = group_results_by_calendar_year(results)
    return list(by_y.get(year_index, []))


def _fmt_warmup_cell(x: float) -> str:
    if x != x:
        return "n/a"
    return f"{x:.6g}"


def warmup_diagnostic_table_rows(results: list[PeriodResult]) -> list[list[str]] | None:
    """Zeilen für Tabelle Warmup: ``Σ ecu_preis·BudgetT`` (Monat) vs. ``ecumenge_ziel_sim/12`` (CLI/Web)."""
    rrows: list[list[str]] = []
    for r in results:
        if r.warmup_diag_sum_ecu_preis_budget_T_monthly is None or r.warmup_diag_ecumenge_ziel_sim_monthly is None:
            continue
        sm = r.warmup_diag_sum_ecu_preis_budget_T_monthly
        em = r.warmup_diag_ecumenge_ziel_sim_monthly
        d_m = sm - em
        d_y = d_m * float(MONTHS_PER_YEAR)
        rrows.append(
            [str(r.period), _fmt_warmup_cell(sm), _fmt_warmup_cell(em), _fmt_warmup_cell(d_m), _fmt_warmup_cell(d_y)]
        )
    return rrows if rrows else None
