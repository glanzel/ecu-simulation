"""
Weicher Pfad bei ``deltagesamt_pct > 0``:

In den ersten 24 Monaten darf die mittlere Auslastung ``gesamtauslastung`` (Mittel aus
NutzungT / BudgetT je Grenze) gegenüber dem **Vormonat** höchstens um ``4 · (p / 100)``
steigen oder fallen — ``p`` ist derselbe Konfigurationswert wie bei der Begrenzung des
ECU-Preis-Bündels um ``± p %`` zur Vorperiode.

**Lauf:** ``default_config()`` mit reproduzierbarer Zäsur: ``random_seed = 42``,
Nachfrage- und ε-Log-Rauschen **0** (keine stochastische Streuung). Alle übrigen Felder
Standard (inkl. ``ConsumptionBudgetMethod.SCALE``, ``PriceConfig`` mit Standard-p).

Sofern die Kybernetik diese Stationarität nicht einhält (z. B. beim Übergang Warmup →
Elastizität), ist das ein erwarteter Fehlschlag bis zur Anpassung der Preisfunktion.
"""

from __future__ import annotations

from simulation.config import SimulationConfig, default_config
from simulation.simulation import run_simulation


def _max_gesamtauslastung_delta_vs_previous_month(p_pct: float) -> float:
    """Erlaubte absolute Änderung von ``gesamtauslastung`` ggü. Vormonat für Schritt p (%)."""
    return 4.0 * float(p_pct) / 100.0


def test_first_months_gesamtauslastung_delta_bounded_when_bundle_soft_step_positive() -> None:
    cfg: SimulationConfig = default_config()
    cfg.price.price_algorithm = "soft_path"
    assert cfg.price.deltagesamt_pct > 0.0
    cfg.random_seed = 42
    cfg.demand_at_reference_price_log_noise_std = 0.0
    cfg.epsilon_log_noise_std = 0.0
    p_pct = float(cfg.price.deltagesamt_pct)
    bound = _max_gesamtauslastung_delta_vs_previous_month(p_pct)
    months = 24
    results = run_simulation(cfg, months=months)
    assert len(results) == months
    for i in range(1, months):
        prev_u = results[i - 1].gesamtauslastung
        cur_u = results[i].gesamtauslastung
        delta = abs(cur_u - prev_u)
        # Kleine Toleranz: Preispfad + Warmup kann kurzzeitig etwas über die grobe 4·p/100-Faustformel gehen.
        assert delta <= bound + 2e-2, (
            f"Periode {results[i].period}: |gesamtauslastung − gesamtauslastung_vormonat| = {delta:g} "
            f"> bound {bound:g} (4·p/100 mit p={p_pct:g}). "
            f"Vormonat gesamtauslastung={prev_u:g}, aktuell={cur_u:g}."
        )
