"""
JSON-Nutzlast für Chart.js auf der Reportseite (reine UI-Ausleitung aus ``PeriodResult``).
"""

from __future__ import annotations

import json
from typing import Any

from ecu.logic.planetary_constants import ALL_BOUNDARIES
from ecu.logic.observations import MONTHS_PER_YEAR
from ecu.simulation.simulation import PeriodResult


def _num_json(x: float) -> float | None:
    if x != x:
        return None
    return float(x)


def chart_payload_dict(results: list[PeriodResult]) -> dict[str, Any]:
    if not results:
        return {
            "labels": [],
            "boundaries": [],
            "meanUtilization": [],
            "bundle_ecu_T": [],
            "ecu_ist_T": [],
            "ecumenge_ziel_J_T": [],
            "ecumenge_ziel_sim_J_T": [],
            "ecumenge_T": [],
            "pctVetSeries": [],
            "priceSeries": [],
        }
    inv_y = 1.0 / float(MONTHS_PER_YEAR)
    labels = [str(r.period) for r in results]
    boundaries = [{"key": b.key, "label": b.label_de} for b in ALL_BOUNDARIES]
    mean_u = [_num_json(r.mean_utilization) for r in results]
    bundle_m = [_num_json(r.bundle_ecu * inv_y) for r in results]
    exp = [_num_json(r.ecu_ist_T) for r in results]
    ziel_cfg_m = [_num_json(r.ecumenge_ziel_J * inv_y) for r in results]
    ziel_sim_m = [_num_json(r.consumption_timeline.ecumenge_ziel_sim_J * inv_y) for r in results]
    cap_m = [_num_json(r.ecumenge_T) for r in results]
    pct_vet_series: list[list[float | None]] = []
    price_series: list[list[float | None]] = []
    for b in ALL_BOUNDARIES:
        k = b.key
        pct_row: list[float | None] = []
        price_row: list[float | None] = []
        for r in results:
            v = r.vet_soll[k]
            c = r.vej_ist[k]
            pct = (100.0 * c / v) if v > 0 else float("nan")
            pct_row.append(_num_json(pct))
            price_row.append(_num_json(r.prices[k]))
        pct_vet_series.append(pct_row)
        price_series.append(price_row)
    return {
        "labels": labels,
        "boundaries": boundaries,
        "meanUtilization": mean_u,
        "bundle_ecu_T": bundle_m,
        "ecu_ist_T": exp,
        "ecumenge_ziel_J_T": ziel_cfg_m,
        "ecumenge_ziel_sim_J_T": ziel_sim_m,
        "ecumenge_T": cap_m,
        "pctVetSeries": pct_vet_series,
        "priceSeries": price_series,
    }


def chart_data_json_for_report(results: list[PeriodResult]) -> str:
    raw = json.dumps(chart_payload_dict(results), ensure_ascii=False, separators=(",", ":"))
    return raw.replace("</script>", "<\\/script>")
