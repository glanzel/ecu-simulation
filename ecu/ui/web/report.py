"""
Report-HTML: Implementierung in ``report_view.px`` (PyJSX); dieses Modul ist die
stabile Import-Adresse ``ecu.ui.web.report`` (echte ``.py``-Datei, damit
Uvicorn ``--reload`` und der Import-Cache nicht mit einer veralteten ``report_page``-
Signatur hängen bleiben).
"""

from __future__ import annotations

import pyjsx.auto_setup  # noqa: F401 — vor Import aus ``.px``

from ecu.ui.web.report_view import report_page

__all__ = ["report_page"]
