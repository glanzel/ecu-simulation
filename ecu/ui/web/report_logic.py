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

RUN_PARAMS_HDR: list[str] = ["EcuJ", "Jahre", "Budget", "σ dem.", "σ ε", "Seed"]
YEARLY_ECU_HDR: list[str] = ["Jahr", "Σ p·VEJ", "Slack", "Ø Auslast."]
MONTH_HDR: list[str] = ["Mon", "p", "consumption", "p·c", "N. p_ref", "VET", "c/VET %"]
YEAR_HDR: list[str] = ["Jahr", "Ø p", "Σ consumption", "Σ N. p_ref", "Σ p·c", "VEJ", "Σc/VEJ %"]
BOUNDARY_SUMMARY_HDR: list[str] = ["Grenze", "Σ consumption", "Σ N. p_ref", "Σ p·c", "VEJ", "Σc/VEJ %"]


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
    """``v`` ist Anteil 0…1; Anzeige als Prozent der VEJ."""
    parts = [f"{k} {fmt_num(v * 100.0, prec=2)} %" for k, v in start_demand_by_boundary]
    return " · ".join(parts)


def run_params_row(
    ecu_per_year: float,
    periods_years: int,
    budget_method: str,
    demand_noise_std: float,
    epsilon_noise_std: float,
    seed: int | None,
) -> list[str]:
    return [
        fmt_num(ecu_per_year),
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
                fmt_num(m.consumption),
                fmt_num(m.pc),
                fmt_num(m.demand),
                fmt_num(m.vet),
                fmt_pct(m.pct_vet),
            ]
        )
    return rrows


def year_summary_values(ys: BoundaryYearSummary) -> list[str]:
    return [
        str(ys.year_index),
        fmt_num(ys.mean_price),
        fmt_num(ys.sum_consumption),
        fmt_num(ys.sum_demand_ref),
        fmt_num(ys.sum_pc),
        fmt_num(ys.vej),
        fmt_pct(ys.pct_sumc_vej),
    ]


def boundary_summary_row(section: BoundarySection) -> list[str]:
    t = section.total
    return [
        f"{section.label} ({section.key})",
        fmt_num(t.sum_consumption),
        fmt_num(t.sum_demand_ref),
        fmt_num(t.sum_pc),
        fmt_num(t.vej),
        fmt_pct(t.pct_sumc_vej),
    ]
