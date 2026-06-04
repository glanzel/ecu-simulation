"""
Auswertungsseite: reine Logik (Zahlen/Zeichenketten/Rasterdaten), keine JSX.
"""

from __future__ import annotations

from ecu.simulation.report_aggregates import BoundaryYearSummary, YearlyEcuSummary
from ecu.ui.web.view_model import BoundarySection, MonthRow

# Für Tailwind-JIT: alle grid-cols-n als Literale in Templates verwenden.
GRID_COLS: tuple[str, ...] = (
    "grid-cols-1",
    "grid-cols-2",
    "grid-cols-3",
    "grid-cols-4",
    "grid-cols-5",
    "grid-cols-6",
    "grid-cols-7",
    "grid-cols-8",
    "grid-cols-9",
    "grid-cols-10",
    "grid-cols-11",
    "grid-cols-12",
)

STYLE_COLS_5_EQ: str = "grid-template-columns: repeat(5, minmax(0, 1fr))"
STYLE_COLS_6_EQ: str = "grid-template-columns: repeat(6, minmax(0, 1fr))"
STYLE_COLS_7_EQ: str = "grid-template-columns: repeat(7, minmax(0, 1fr))"

REPORT_GAP: str = "gap-1"
FORM_INPUT: str = (
    "w-full border border-slate-200 rounded-sm px-2 py-1.5 text-sm text-slate-800 "
    "bg-white focus:outline-none focus:ring-1 focus:ring-report-accent/40"
)

RUN_PARAMS_HDR: list[str] = ["ecumenge_ziel_J", "Jahre", "Budget", "σ dem.", "σ ε", "Seed"]
YEARLY_ECU_HDR: list[str] = ["Jahr", "Ecu VEJ-Ziel ges. (Jahr)", "Slack", "Ø Auslast."]
MONTH_HDR: list[str] = ["Mon", "p", "VEJ-Ist", "Ecu VEJ-Ist", "Demand", "VET-Ziel", "Ist / VET-Ziel %"]
YEAR_HDR: list[str] = ["Jahr", "Ø p", "Σ VEJ-Ist", "Σ Demand", "Σ Ecu VEJ-Ist", "VEJ-Ziel", "Σ Ist / Ziel %"]
BOUNDARY_SUMMARY_HDR: list[str] = ["Grenze", "Σ VEJ-Ist", "Σ Demand", "Σ Ecu VEJ-Ist", "VEJ-Ziel", "Σ Ist / Ziel %"]


def fmt_num(x: float, prec: int = 6) -> str:
    if x != x:
        return "n/a"
    return f"{x:.{prec}g}"


def fmt_pct(x: float) -> str:
    if x != x:
        return "n/a"
    return f"{x:.2f}"


def fmt_seed(s: int | None) -> str:
    if s is None:
        return "—"
    return str(s)


def growth_one_line(growth_by_boundary: list[tuple[str, float]]) -> str:
    """``v`` ist Jahresfaktor; Anzeige als Index (100 = Basis)."""
    parts: list[str] = []
    for k, v in growth_by_boundary:
        idx = v * 100.0
        if idx == int(idx):
            parts.append(f"{k} {int(idx)}")
        else:
            parts.append(f"{k} {fmt_num(idx, prec=4)}")
    return " · ".join(parts)


def start_demand_one_line(start_demand_by_boundary: list[tuple[str, float]]) -> str:
    """``v`` ist Anteil 0…1; Anzeige als Prozent des VEJ-Ziels."""
    parts = [f"{k} {fmt_num(v * 100.0, prec=2)} %" for k, v in start_demand_by_boundary]
    return " · ".join(parts)


def run_params_row(
    ecumenge_ziel_J: float,
    periods_years: int,
    budget_method: str,
    demand_noise_std: float,
    epsilon_noise_std: float,
    seed: int | None,
) -> list[str]:
    return [
        fmt_num(ecumenge_ziel_J),
        str(periods_years),
        budget_method,
        fmt_num(demand_noise_std),
        fmt_num(epsilon_noise_std),
        fmt_seed(seed),
    ]


def yearly_ecu_table_rows(rows: list[YearlyEcuSummary]) -> list[list[str]] | None:
    if not rows:
        return None
    rrows: list[list[str]] = []
    for y in rows:
        rrows.append(
            [
                str(y.year_index),
                fmt_num(y.bundle_ecu),
                fmt_num(y.slack_vej),
                fmt_pct(y.mean_utilization),
            ]
        )
    return rrows


def month_table_rows(months: list[MonthRow]) -> list[list[str]]:
    rrows: list[list[str]] = []
    for m in months:
        rrows.append(
            [
                str(m.period),
                fmt_num(m.price),
                fmt_num(m.vej_ist),
                fmt_num(m.pc),
                fmt_num(m.demand),
                fmt_num(m.vet_ziel),
                fmt_pct(m.pct_vet_ziel),
            ]
        )
    return rrows


def year_summary_values(ys: BoundaryYearSummary) -> list[str]:
    return [
        str(ys.year_index),
        fmt_num(ys.mean_price),
        fmt_num(ys.sum_vej_ist),
        fmt_num(ys.sum_demand_ref),
        fmt_num(ys.sum_pc),
        fmt_num(ys.vej_ziel),
        fmt_pct(ys.pct_vej_ist_jahr_vs_vej_ziel),
    ]


def boundary_summary_row(section: BoundarySection) -> list[str]:
    t = section.total
    return [
        f"{section.label} ({section.key})",
        fmt_num(t.sum_vej_ist),
        fmt_num(t.sum_demand_ref),
        fmt_num(t.sum_pc),
        fmt_num(t.vej_ziel),
        fmt_pct(t.pct_vej_ist_jahr_vs_vej_ziel),
    ]
