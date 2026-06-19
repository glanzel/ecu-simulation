"""
Daten für die Web-Auswertungsseite (ohne JSX): eine Sektion pro Grenze, verschachtelt Jahr → Monate.
"""

from __future__ import annotations

from dataclasses import dataclass

from logic.planetary_constants import ALL_BOUNDARIES
from simulation.report_aggregates import (
    BoundaryTotalSummary,
    BoundaryYearSummary,
    boundary_total_summary,
    boundary_year_summaries,
    months_for_calendar_year,
)
from simulation.simulation import PeriodResult
from ui.web.i18n import SimulationI18n


@dataclass
class MonthRow:
    period: int
    price: float
    vej_ist: float
    pc: float
    demand: float
    vet_ziel: float
    pct_vet_ziel: float


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
        c = r.vej_ist[boundary_key]
        v = r.vet_ziel[boundary_key]
        pc = p * c
        pct = (100.0 * c / v) if v > 0 else float("nan")
        rows.append(
            MonthRow(
                period=r.period,
                price=p,
                vej_ist=c,
                pc=pc,
                demand=r.demand_at_reference_price[boundary_key],
                vet_ziel=v,
                pct_vet_ziel=pct,
            )
        )
    return rows


def build_boundary_sections(results: list[PeriodResult], *, i18n: SimulationI18n) -> list[BoundarySection]:
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
                label=i18n.boundary_label(k, fallback=b.label_de),
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
