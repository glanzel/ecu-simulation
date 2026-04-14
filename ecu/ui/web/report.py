"""
Stabile Import-Adresse ``ecu.ui.web.report``; JSX-View in ``report_view``.

``import pyjsx.auto_setup`` vor dem ersten Import dieses Moduls (z. B. in ``app.py``).

Die Report-Route in FastAPI: ``ecu.ui.web.app:report`` — ``@app.get("/report", ...)``.
"""

from __future__ import annotations

import pyjsx.auto_setup  # noqa: F401 — .px-Imports + Codec

from ecu.ui.web.report_view import (
    BoundaryBlock,
    DataGrid,
    GlobalYearlyEcuBlock,
    MonthGrid,
    RunParamsBlock,
    YearBlock,
    YearHeaderRow,
    report_page,
)

__all__ = [
    "BoundaryBlock",
    "DataGrid",
    "GlobalYearlyEcuBlock",
    "MonthGrid",
    "RunParamsBlock",
    "YearBlock",
    "YearHeaderRow",
    "report_page",
]
