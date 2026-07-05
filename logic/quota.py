"""Quote_t und Delta_t je Grenze (Text-Algorithmus)."""

from __future__ import annotations

from dataclasses import dataclass

from logic.observations import BOUNDARY_KEYS


@dataclass(frozen=True)
class BoundaryQuotaStep:
    """Quota- und Delta-Werte für einen Zeitschritt t."""

    auslastung: dict[str, float]
    gesamtauslastung: float
    gesamtauslastung_t0: float
    quote_T: dict[str, float]
    delta_T: dict[str, float]
    absenkung_f: float
    absenkung: bool


class QuotaCalculator:
    """Berechnet Auslastung, Gesamtauslastung, Quote_t und Delta_t aus Nutzung und Budget."""

    @staticmethod
    def auslastung_from_nutzung_budget(nutzung_T: dict[str, float], budget_T: dict[str, float]) -> dict[str, float]:
        return {k: (nutzung_T[k] / budget_T[k] if budget_T[k] > 0.0 else 0.0) for k in BOUNDARY_KEYS}

    @staticmethod
    def gesamtauslastung_from_auslastung(auslastung: dict[str, float]) -> float:
        return sum(auslastung[k] for k in BOUNDARY_KEYS) / float(len(BOUNDARY_KEYS))

    @staticmethod
    def quote_t_interpolated(nutzung_t0: dict[str, float], budget_T: dict[str, float], f: float) -> dict[str, float]:
        """``Quote_t_k = Nutzung_t0_k·(1−f) + Budget_t_k·f``."""
        return {k: nutzung_t0[k] * (1.0 - f) + budget_T[k] * f for k in BOUNDARY_KEYS}

    @classmethod
    def from_nutzung_budget(
        cls,
        nutzung_T: dict[str, float],
        budget_T: dict[str, float],
        nutzung_t0: dict[str, float],
        absenkung_f_prev: float,
        deltagesamt_frac: float,
    ) -> BoundaryQuotaStep:
        auslastung = cls.auslastung_from_nutzung_budget(nutzung_T, budget_T)
        gesamtauslastung = cls.gesamtauslastung_from_auslastung(auslastung)
        auslastung_t0 = cls.auslastung_from_nutzung_budget(nutzung_t0, budget_T)
        gesamtauslastung_t0 = cls.gesamtauslastung_from_auslastung(auslastung_t0)
        absenkung = gesamtauslastung > 1.0
        f = min(1.0, absenkung_f_prev + deltagesamt_frac) if absenkung else absenkung_f_prev
        quote_T = cls.quote_t_interpolated(nutzung_t0, budget_T, f) if f < 1.0 else {k: budget_T[k] for k in BOUNDARY_KEYS}
        delta_T: dict[str, float] = {}
        eps = 1e-15
        for k in BOUNDARY_KEYS:
            delta_T[k] = (deltagesamt_frac * auslastung[k] / max(eps, gesamtauslastung)) if gesamtauslastung > eps else 0.0
        return BoundaryQuotaStep(
            auslastung=auslastung,
            gesamtauslastung=gesamtauslastung,
            gesamtauslastung_t0=gesamtauslastung_t0,
            quote_T=quote_T,
            delta_T=delta_T,
            absenkung_f=f,
            absenkung=absenkung,
        )
