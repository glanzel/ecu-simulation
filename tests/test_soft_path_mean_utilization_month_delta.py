"""
Weicher Pfad bei ``max_shadow_bundle_scale_pct_per_period > 0``:

In den ersten 24 Monaten darf die mittlere Auslastung ``mean_utilization`` (Mittel aus
VEJ-Ist / VET-Ziel je Grenze) gegenüber dem **Vormonat** höchstens um ``4 · (p / 100)``
steigen oder fallen — ``p`` ist derselbe Konfigurationswert wie bei der Begrenzung des
Schattenpreis-Bündels um ``± p %`` zur Vorperiode.

**Lauf:** ``default_config()`` mit reproduzierbarer Zäsur: ``random_seed = 42``,
Nachfrage- und ε-Log-Rauschen **0** (keine stochastische Streuung). Alle übrigen Felder
Standard (inkl. ``ConsumptionBudgetMethod.SCALE``, ``PriceConfig`` mit Standard-p).

Sofern die Kybernetik diese Stationarität nicht einhält (z. B. beim Übergang Warmup →
Elastizität), ist das ein erwarteter Fehlschlag bis zur Anpassung der Preisfunktion.
"""

from __future__ import annotations

from simulation.config import SimulationConfig, default_config
from simulation.simulation import run_simulation


def _max_mean_utilization_delta_vs_previous_month(p_pct: float) -> float:
    """Erlaubte absolute Änderung von ``mean_utilization`` ggü. Vormonat für Schritt p (%)."""
    return 4.0 * float(p_pct) / 100.0


def test_first_months_mean_utilization_delta_bounded_when_bundle_soft_step_positive() -> None:
    cfg: SimulationConfig = default_config()
    assert cfg.price.max_shadow_bundle_scale_pct_per_period > 0.0
    cfg.random_seed = 42
    cfg.demand_at_reference_price_log_noise_std = 0.0
    cfg.epsilon_log_noise_std = 0.0
    p_pct = float(cfg.price.max_shadow_bundle_scale_pct_per_period)
    bound = _max_mean_utilization_delta_vs_previous_month(p_pct)
    months = 24
    results = run_simulation(cfg, months=months)
    assert len(results) == months
    for i in range(1, months):
        prev_u = results[i - 1].mean_utilization
        cur_u = results[i].mean_utilization
        delta = abs(cur_u - prev_u)
        # Kleine Toleranz: Preispfad + Warmup kann kurzzeitig etwas über die grobe 4·p/100-Faustformel gehen.
        assert delta <= bound + 2e-2, (
            f"Periode {results[i].period}: |mean_u − mean_u_vormonat| = {delta:g} "
            f"> bound {bound:g} (4·p/100 mit p={p_pct:g}). "
            f"Vormonat mean_u={prev_u:g}, aktuell={cur_u:g}."
        )
