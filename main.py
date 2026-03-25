"""CLI-Einstieg: ``python main.py`` oder ``python -m ecu_simulation``.

Direktaufruf ``python main.py``: Das Paket ``ecu_simulation`` liegt eine Ebene
darüber; das Elternverzeichnis muss auf ``sys.path``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from ecu_simulation.config import BOUNDARY_KEYS, SimulationConfig, default_config
from ecu_simulation.simulation import print_report, run_simulation


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ECU-Terminalsimulation")
    p.add_argument("--ecu", type=float, default=None, help="Start-EcuJ pro Jahr")
    p.add_argument("--periods", type=int, default=20, help="Anzahl Perioden")
    p.add_argument(
        "--growth-co2",
        type=float,
        dest="growth_co2",
        default=1.0,
        help="Multiplikativer Nachfrage-Faktor pro Periode (nur CO₂)",
    )
    p.add_argument(
        "--demand-noise-std",
        type=float,
        default=None,
        metavar="σ",
        help=(
            "Std.-Abw. im Log-Raum für Rauschen auf demand_at_reference_price pro Periode "
            "(nach Wachstum); 0 = aus. Standard aus Konfiguration (typ. 0,3)."
        ),
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Zufalls-Seed für reproduzierbare Läufe (optional).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg: SimulationConfig = default_config()
    if args.ecu is not None:
        cfg.ecu_per_year = args.ecu
    if args.demand_noise_std is not None:
        cfg.demand_at_reference_price_log_noise_std = args.demand_noise_std
    if args.seed is not None:
        cfg.random_seed = args.seed
    growth = {k: 1.0 for k in BOUNDARY_KEYS}
    growth["co2"] = args.growth_co2
    results = run_simulation(cfg, args.periods, demand_growth_per_period=growth)
    print_report(results, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
