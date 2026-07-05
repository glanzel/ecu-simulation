"""Kybernetischer Elastikfaktor je Grenze (Text-Algorithmus ab Preisschritt 5)."""

from __future__ import annotations

from logic.observations import BOUNDARY_KEYS, ConsumptionTimeline
from logic.quota import QuotaCalculator


class ElasticityFactorTracker:
    """Pro Grenze ein Elastikfaktor; Start 1, Anpassung bei Abweichung Nutzung vs. QuoteT."""

    def __init__(self) -> None:
        self.factors: dict[str, float] = {k: 1.0 for k in BOUNDARY_KEYS}

    def copy(self) -> ElasticityFactorTracker:
        out = ElasticityFactorTracker()
        out.factors = dict(self.factors)
        return out

    def initialize_from_timeline(self, timeline: ConsumptionTimeline, deltagesamt_frac: float) -> None:
        """Elastikfaktor_start = Ø(NutzungT / QuoteT) über die Timeline (Text)."""
        if len(timeline) == 0:
            return
        sums: dict[str, float] = {k: 0.0 for k in BOUNDARY_KEYS}
        counts: dict[str, int] = {k: 0 for k in BOUNDARY_KEYS}
        nutzung_t0 = {k: timeline[0].nutzung_T_for(k) for k in BOUNDARY_KEYS}
        absenkung_f = 0.0
        for idx in range(len(timeline)):
            iv = timeline[idx]
            budget_T = {k: iv.budget_T_for(k) for k in BOUNDARY_KEYS}
            nutzung_T = {k: iv.nutzung_T_for(k) for k in BOUNDARY_KEYS}
            quota = QuotaCalculator.from_nutzung_budget(nutzung_T, budget_T, nutzung_t0, absenkung_f, deltagesamt_frac)
            absenkung_f = quota.absenkung_f
            for k in BOUNDARY_KEYS:
                q = quota.quote_T[k]
                if q > 1e-15:
                    sums[k] += nutzung_T[k] / q
                    counts[k] += 1
        for k in BOUNDARY_KEYS:
            if counts[k] > 0:
                self.factors[k] = max(0.01, sums[k] / float(counts[k]))

    def update_boundary(self, boundary_key: str, nutzung_T: float, quote_T: float, alpha: float) -> None:
        if quote_T <= 1e-15 or alpha <= 0.0:
            return
        ratio = nutzung_T / quote_T - 1.0
        if ratio > 0.0:
            self.factors[boundary_key] = max(0.01, self.factors[boundary_key] * (1.0 + alpha * ratio))

    def factor_for(self, boundary_key: str) -> float:
        return self.factors[boundary_key]
