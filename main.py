"""CLI-Einstieg: ``python main.py`` oder ``python -m ecu_simulation``.

Direktaufruf ``python main.py``: Das Paket ``ecu_simulation`` liegt eine Ebene
darüber; das Elternverzeichnis muss auf ``sys.path``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from ecu_simulation.simulation.cli_simulation import main


if __name__ == "__main__":
    raise SystemExit(main())
