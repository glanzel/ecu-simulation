"""
Aggregation von ``PeriodResult``-Listen für Jahres-/Grenz-Auswertungen (CLI und Web).
"""

from __future__ import annotations

from dataclasses import dataclass

from logic.observations import MONTHS_PER_YEAR
from simulation.simulation import PeriodResult

WARMUP_DIAG_TABLE_HEADER: list[str] = [
    "Mon",
    "Σ p·VET-Ziel (Mon.)",
    "ecumenge_ziel_sim_J/12",
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
    ecumenge_ziel_J: float
    sum_ecu_ist_J: float
    bundle_ecu: float
    slack_vej: float
    mean_utilization: float


@dataclass
class BoundaryTotalSummary:
    """Gesamtlauf über alle Monate für eine Grenze."""

    boundary_key: str
    sum_vej_ist: float
    sum_demand_ref: float
    sum_pc: float
    vej_ziel: float
    pct_vej_ist_jahr_vs_vej_ziel: float


@dataclass
class BoundaryYearSummary:
    """Ein Kalenderjahr für eine Grenze (wie CLI-Jahresübersicht)."""

    year_index: int
    n_months: int
    mean_price: float
    sum_vej_ist: float
    sum_demand_ref: float
    sum_pc: float
    vej_ziel: float
    pct_vej_ist_jahr_vs_vej_ziel: float


def yearly_ecu_summaries(results: list[PeriodResult]) -> list[YearlyEcuSummary]:
    """Jährliche Summen Σ p·c (verbuchte ECU) und Rahmengrößen — alle Grenzen zusammen."""
    by_y = group_results_by_calendar_year(results)
    out: list[YearlyEcuSummary] = []
    for y in sorted(by_y.keys()):
        mrows = by_y[y]
        n = len(mrows)
        sum_pc = sum(x.ecu_ist_T for x in mrows)
        last = mrows[-1]
        slack = last.bundle_ecu - last.ecumenge_ziel_J
        mean_u = sum(x.mean_utilization for x in mrows) / float(n)
        out.append(
            YearlyEcuSummary(
                year_index=y,
                n_months=n,
                ecumenge_ziel_J=last.ecumenge_ziel_J,
                sum_ecu_ist_J=sum_pc,
                bundle_ecu=last.bundle_ecu,
                slack_vej=slack,
                mean_utilization=mean_u,
            )
        )
    return out


def boundary_total_summary(results: list[PeriodResult], boundary_key: str) -> BoundaryTotalSummary:
    """Summen über den gesamten Lauf; VEJ-Ziel aus letztem Monat (konstant)."""
    if not results:
        return BoundaryTotalSummary(
            boundary_key=boundary_key,
            sum_vej_ist=0.0,
            sum_demand_ref=0.0,
            sum_pc=0.0,
            vej_ziel=0.0,
            pct_vej_ist_jahr_vs_vej_ziel=float("nan"),
        )
    sum_c = sum(r.vej_ist[boundary_key] for r in results)
    sum_d = sum(r.demand_at_reference_price[boundary_key] for r in results)
    sum_pc = sum(r.prices[boundary_key] * r.vej_ist[boundary_key] for r in results)
    vej_ziel = results[-1].vej_ziel[boundary_key]
    pct = (100.0 * sum_c / vej_ziel) if vej_ziel > 0 else float("nan")
    return BoundaryTotalSummary(
        boundary_key=boundary_key,
        sum_vej_ist=sum_c,
        sum_demand_ref=sum_d,
        sum_pc=sum_pc,
        vej_ziel=vej_ziel,
        pct_vej_ist_jahr_vs_vej_ziel=pct,
    )


def boundary_year_summaries(results: list[PeriodResult], boundary_key: str) -> list[BoundaryYearSummary]:
    """Sortierte Liste je Kalenderjahr."""
    by_y = group_results_by_calendar_year(results)
    rows: list[BoundaryYearSummary] = []
    for y in sorted(by_y.keys()):
        mrows = by_y[y]
        n = len(mrows)
        sum_c = sum(x.vej_ist[boundary_key] for x in mrows)
        sum_d = sum(x.demand_at_reference_price[boundary_key] for x in mrows)
        sum_pc = sum(x.prices[boundary_key] * x.vej_ist[boundary_key] for x in mrows)
        mean_p = sum(x.prices[boundary_key] for x in mrows) / float(n)
        vej_ziel = mrows[-1].vej_ziel[boundary_key]
        pct = (100.0 * sum_c / vej_ziel) if vej_ziel > 0 else float("nan")
        rows.append(
            BoundaryYearSummary(
                year_index=y,
                n_months=n,
                mean_price=mean_p,
                sum_vej_ist=sum_c,
                sum_demand_ref=sum_d,
                sum_pc=sum_pc,
                vej_ziel=vej_ziel,
                pct_vej_ist_jahr_vs_vej_ziel=pct,
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
    """Zeilen für Tabelle Warmup: ``Σ p·VET`` (Monat) vs. ``ecumenge_ziel_sim_J/12`` (CLI/Web)."""
    rrows: list[list[str]] = []
    for r in results:
        if r.warmup_diag_sum_p_vet_ziel_monthly is None or r.warmup_diag_ecumenge_ziel_sim_monthly is None:
            continue
        sm = r.warmup_diag_sum_p_vet_ziel_monthly
        em = r.warmup_diag_ecumenge_ziel_sim_monthly
        d_m = sm - em
        d_y = d_m * float(MONTHS_PER_YEAR)
        rrows.append(
            [str(r.period), _fmt_warmup_cell(sm), _fmt_warmup_cell(em), _fmt_warmup_cell(d_m), _fmt_warmup_cell(d_y)]
        )
    return rrows if rrows else None
