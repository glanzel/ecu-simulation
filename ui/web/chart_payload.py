"""
JSON-Nutzlast für Chart.js auf der Reportseite (reine UI-Ausleitung aus ``PeriodResult``).
"""

from __future__ import annotations

import json
from typing import Any

from logic.planetary_constants import ALL_BOUNDARIES
from logic.observations import MONTHS_PER_YEAR
from simulation.simulation import PeriodResult
from ui.web.i18n import SimulationI18n


def _num_json(x: float) -> float | None:
    if x != x:
        return None
    return float(x)


def chart_payload_dict(results: list[PeriodResult], *, i18n: SimulationI18n) -> dict[str, Any]:
    if not results:
        return {
            "labels": [],
            "boundaries": [],
            "meanUtilization": [],
            "ecumenge_kontenrahmen_T": [],
            "ecu_ist_T": [],
            "ecumenge_ziel_T": [],
            "ecumenge_ziel_sim_T": [],
            "ecumenge_T": [],
            "pctVetZielSeries": [],
            "priceSeries": [],
            "elastikfaktorSeries": [],
            "chartLabels": i18n.chart_labels(),
        }
    inv_y = 1.0 / float(MONTHS_PER_YEAR)
    labels = [str(r.period) for r in results]
    boundaries = [
        {"key": b.key, "label": i18n.boundary_label(b.key, fallback=b.label_de)}
        for b in ALL_BOUNDARIES
    ]
    gesamtauslastung = [_num_json(r.gesamtauslastung) for r in results]
    bundle_m = [_num_json(r.ecumenge_kontenrahmen * inv_y) for r in results]
    exp = [_num_json(r.ecu_ist_T) for r in results]
    ziel_cfg_m = [_num_json(r.ecumenge_ziel * inv_y) for r in results]
    ziel_sim_m = [_num_json(r.consumption_timeline.ecumenge_ziel_sim * inv_y) for r in results]
    cap_m = [_num_json(r.ecumenge_T) for r in results]
    pct_budget_T_series: list[list[float | None]] = []
    price_series: list[list[float | None]] = []
    elastikfaktor_series: list[list[float | None]] = []
    for b in ALL_BOUNDARIES:
        k = b.key
        pct_row: list[float | None] = []
        price_row: list[float | None] = []
        elastik_row: list[float | None] = []
        for r in results:
            v = r.budget_T[k]
            c = r.nutzung_T[k]
            pct = (100.0 * c / v) if v > 0 else float("nan")
            pct_row.append(_num_json(pct))
            price_row.append(_num_json(r.prices[k]))
            elastik_row.append(_num_json(r.elastikfaktor[k]))
        pct_budget_T_series.append(pct_row)
        price_series.append(price_row)
        elastikfaktor_series.append(elastik_row)
    return {
        "labels": labels,
        "boundaries": boundaries,
        "meanUtilization": gesamtauslastung,
        "ecumenge_kontenrahmen_T": bundle_m,
        "ecu_ist_T": exp,
        "ecumenge_ziel_T": ziel_cfg_m,
        "ecumenge_ziel_sim_T": ziel_sim_m,
        "ecumenge_T": cap_m,
        "pctVetZielSeries": pct_budget_T_series,
        "priceSeries": price_series,
        "elastikfaktorSeries": elastikfaktor_series,
        "chartLabels": i18n.chart_labels(),
    }


def chart_data_json_for_report(results: list[PeriodResult], *, i18n: SimulationI18n) -> str:
    raw = json.dumps(chart_payload_dict(results, i18n=i18n), ensure_ascii=False, separators=(",", ":"))
    return raw.replace("</script>", "<\\/script>")
