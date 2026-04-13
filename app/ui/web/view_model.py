"""
Daten für die Web-Auswertungsseite (ohne JSX): eine Sektion pro Grenze, verschachtelt Jahr → Monate.
"""

from __future__ import annotations

from dataclasses import dataclass

from ecu_simulation.logic.planetary_constants import ALL_BOUNDARIES
from ecu_simulation.simulation.report_aggregates import (
    BoundaryTotalSummary,
    BoundaryYearSummary,
    boundary_total_summary,
    boundary_year_summaries,
    months_for_calendar_year,
)
from ecu_simulation.simulation.simulation import PeriodResult


@dataclass
class MonthRow:
    period: int
    price: float
    consumption: float
    pc: float
    demand: float
    vet: float
    pct_vet: float


@dataclass
class YearDetail:
    summary: BoundaryYearSummary
    months: list[MonthRow]


@dataclass
class BoundarySection:
    key: str
    label: str
    total: BoundaryTotalSummary
    years: list[YearDetail]


def _month_rows_for_boundary(
    results: list[PeriodResult],
    boundary_key: str,
) -> list[MonthRow]:
    rows: list[MonthRow] = []
    for r in results:
        p = r.prices[boundary_key]
        c = r.consumption[boundary_key]
        v = r.vet[boundary_key]
        pc = p * c
        pct = (100.0 * c / v) if v > 0 else float("nan")
        rows.append(
            MonthRow(
                period=r.period,
                price=p,
                consumption=c,
                pc=pc,
                demand=r.demand_at_reference_price[boundary_key],
                vet=v,
                pct_vet=pct,
            )
        )
    return rows


def build_boundary_sections(results: list[PeriodResult]) -> list[BoundarySection]:
    """Eine Sektion pro Eintrag in ``ALL_BOUNDARIES`` (Reihenfolge der Konstanten)."""
    sections: list[BoundarySection] = []
    for b in ALL_BOUNDARIES:
        k = b.key
        total = boundary_total_summary(results, k)
        year_summaries = boundary_year_summaries(results, k)
        by_y = group_years_to_months(results, k, year_summaries)
        sections.append(
            BoundarySection(
                key=k,
                label=b.label_de,
                total=total,
                years=by_y,
            )
        )
    return sections


def group_years_to_months(
    results: list[PeriodResult],
    boundary_key: str,
    year_summaries: list[BoundaryYearSummary],
) -> list[YearDetail]:
    out: list[YearDetail] = []
    for ys in year_summaries:
        mlist = months_for_calendar_year(results, ys.year_index)
        months = _month_rows_for_boundary(mlist, boundary_key)
        out.append(YearDetail(summary=ys, months=months))
    return out
