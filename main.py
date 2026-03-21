"""CLI für die ECU-Simulation.

Aufruf aus dem Projektordner (Parent von ``ecu_sim/``), z. B.::

    python ecu_sim/main.py --periods 5

Alternativ: ``python -m ecu_sim`` (nutzt ``ecu_sim/__main__.py``).
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

# Direktaufruf ``python ecu_sim/main.py``: Paket ``ecu_sim`` liegt eine Ebene darüber.
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from ecu_sim.config import SimulationConfig
from ecu_sim.simulation import print_report, run_simulation


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ECU-Terminalsimulation (drei planetare Grenzen).")
    p.add_argument("--periods", type=int, default=8, help="Anzahl Zeitschritte")
    p.add_argument("--seed", type=int, default=None, help="Zufalls-Seed (für künftige Erweiterungen)")
    p.add_argument("--ecu", type=float, default=1.0, help="EcuJ: ECU-Jahresvolumen (Numéraire)")
    p.add_argument(
        "--growth-co2",
        type=float,
        default=1.0,
        metavar="F",
        help="Multiplikator Nachfrage CO2 pro Periode (z. B. 1.02)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.seed is not None:
        random.seed(args.seed)

    cfg = SimulationConfig(ecu_per_year=args.ecu)
    growth = {"co2": args.growth_co2, "hanpp": 1.0, "nitrogen": 1.0}
    results = run_simulation(cfg, periods=args.periods, demand_growth_per_period=growth)
    if args.seed is not None:
        print(f"seed = {args.seed}")
    print_report(results, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
