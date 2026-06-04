"""
Stabile Import-Adresse ``ecu.ui.web.simulation_page``; JSX-View in ``simulation_view``.

``import pyjsx.auto_setup`` vor dem ersten Import dieses Moduls (z. B. in ``app.py``).

Die Simulation-Route in FastAPI: ``ecu.ui.web.app:simulation`` — ``@app.get("/simulation", ...)``.
"""

from __future__ import annotations

import pyjsx.auto_setup  # noqa: F401 — .px-Imports + Codec

from ecu.ui.web.simulation_view import (
    BoundaryBlock,
    ChartsSection,
    DataGrid,
    GlobalYearlyEcuBlock,
    MonthGrid,
    RunParamsBlock,
    SimulationSetupPanel,
    WarmupDiagBlock,
    YearBlock,
    YearHeaderRow,
    simulation_page,
)

__all__ = [
    "BoundaryBlock",
    "ChartsSection",
    "DataGrid",
    "GlobalYearlyEcuBlock",
    "MonthGrid",
    "RunParamsBlock",
    "SimulationSetupPanel",
    "WarmupDiagBlock",
    "YearBlock",
    "YearHeaderRow",
    "simulation_page",
]
