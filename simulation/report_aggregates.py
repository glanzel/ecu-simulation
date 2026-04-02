"""
Aggregation von ``PeriodResult``-Listen für Jahres-/Grenz-Auswertungen (CLI und Web).
"""

from __future__ import annotations

from dataclasses import dataclass

from ecu_simulation.logic.observations import MONTHS_PER_YEAR
from ecu_simulation.simulation.simulation import PeriodResult


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
class BoundaryTotalSummary:
    """Gesamtlauf über alle Monate für eine Grenze."""

    boundary_key: str
    sum_consumption: float
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
    sum_pc: float
    vej: float
    pct_sumc_vej: float


def boundary_total_summary(results: list[PeriodResult], boundary_key: str) -> BoundaryTotalSummary:
    """Summen über den gesamten Lauf; VEJ aus letztem Monat (konstant)."""
    if not results:
        return BoundaryTotalSummary(
            boundary_key=boundary_key,
            sum_consumption=0.0,
            sum_pc=0.0,
            vej=0.0,
            pct_sumc_vej=float("nan"),
        )
    sum_c = sum(r.consumption[boundary_key] for r in results)
    sum_pc = sum(r.prices[boundary_key] * r.consumption[boundary_key] for r in results)
    vej = results[-1].vej[boundary_key]
    pct = (100.0 * sum_c / vej) if vej > 0 else float("nan")
    return BoundaryTotalSummary(
        boundary_key=boundary_key,
        sum_consumption=sum_c,
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
