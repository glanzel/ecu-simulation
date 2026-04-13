"""
Aggregation von ``PeriodResult``-Listen für Jahres-/Grenz-Auswertungen (CLI und Web).
"""

from __future__ import annotations

from dataclasses import dataclass

from ecu.logic.observations import MONTHS_PER_YEAR
from ecu.simulation.simulation import PeriodResult


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
    ecu_per_year: float
    sum_ecu_expenditure: float
    bundle_ecu: float
    slack_vej: float
    mean_utilization: float


@dataclass
class BoundaryTotalSummary:
    """Gesamtlauf über alle Monate für eine Grenze."""

    boundary_key: str
    sum_consumption: float
    sum_demand_ref: float
    sum_pc: float
    vej: float
    pct_sumc_vej: float


@dataclass
class BoundaryYearSummary:
    """Ein Kalenderjahr für eine Grenze (wie CLI-Jahresübersicht)."""

    year_index: int
    n_months: int
    mean_price: float
    sum_consumption: float
    sum_demand_ref: float
    sum_pc: float
    vej: float
    pct_sumc_vej: float


def yearly_ecu_summaries(results: list[PeriodResult]) -> list[YearlyEcuSummary]:
    """Jährliche Summen Σ p·c (verbuchte ECU) und Rahmengrößen — alle Grenzen zusammen."""
    by_y = group_results_by_calendar_year(results)
    out: list[YearlyEcuSummary] = []
    for y in sorted(by_y.keys()):
        mrows = by_y[y]
        n = len(mrows)
        sum_pc = sum(x.ecu_expenditure for x in mrows)
        last = mrows[-1]
        slack = last.bundle_ecu - last.ecu_per_year
        mean_u = sum(x.mean_utilization for x in mrows) / float(n)
        out.append(
            YearlyEcuSummary(
                year_index=y,
                n_months=n,
                ecu_per_year=last.ecu_per_year,
                sum_ecu_expenditure=sum_pc,
                bundle_ecu=last.bundle_ecu,
                slack_vej=slack,
                mean_utilization=mean_u,
            )
        )
    return out


def boundary_total_summary(results: list[PeriodResult], boundary_key: str) -> BoundaryTotalSummary:
    """Summen über den gesamten Lauf; VEJ aus letztem Monat (konstant)."""
    if not results:
        return BoundaryTotalSummary(
            boundary_key=boundary_key,
            sum_consumption=0.0,
            sum_demand_ref=0.0,
            sum_pc=0.0,
            vej=0.0,
            pct_sumc_vej=float("nan"),
        )
    sum_c = sum(r.consumption[boundary_key] for r in results)
    sum_d = sum(r.demand_at_reference_price[boundary_key] for r in results)
    sum_pc = sum(r.prices[boundary_key] * r.consumption[boundary_key] for r in results)
    vej = results[-1].vej[boundary_key]
    pct = (100.0 * sum_c / vej) if vej > 0 else float("nan")
    return BoundaryTotalSummary(
        boundary_key=boundary_key,
        sum_consumption=sum_c,
        sum_demand_ref=sum_d,
        sum_pc=sum_pc,
        vej=vej,
        pct_sumc_vej=pct,
    )


def boundary_year_summaries(results: list[PeriodResult], boundary_key: str) -> list[BoundaryYearSummary]:
    """Sortierte Liste je Kalenderjahr."""
    by_y = group_results_by_calendar_year(results)
    rows: list[BoundaryYearSummary] = []
    for y in sorted(by_y.keys()):
        mrows = by_y[y]
        n = len(mrows)
        sum_c = sum(x.consumption[boundary_key] for x in mrows)
        sum_d = sum(x.demand_at_reference_price[boundary_key] for x in mrows)
        sum_pc = sum(x.prices[boundary_key] * x.consumption[boundary_key] for x in mrows)
        mean_p = sum(x.prices[boundary_key] for x in mrows) / float(n)
        vej = mrows[-1].vej[boundary_key]
        pct = (100.0 * sum_c / vej) if vej > 0 else float("nan")
        rows.append(
            BoundaryYearSummary(
                year_index=y,
                n_months=n,
                mean_price=mean_p,
                sum_consumption=sum_c,
                sum_demand_ref=sum_d,
                sum_pc=sum_pc,
                vej=vej,
                pct_sumc_vej=pct,
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
