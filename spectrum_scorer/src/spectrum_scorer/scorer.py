"""Spectrum-based fault localization using Ochiai, Tarantula, Jaccard, and DStar."""
from typing import Dict, List, Tuple
from .models import Execution


class SpectrumScorer:
    """Computes spectrum-based suspiciousness scores for components.

    Takes execution data (list of Execution objects with involved components
    and pass/fail label) and computes a suspiciousness score per component using
    a chosen spectrum formula.
    """

    FORMULAS = {"ochiai", "tarantula", "jaccard", "dstar"}

    def __init__(self, formula: str = "ochiai"):
        if formula not in self.FORMULAS:
            raise ValueError(f"Unknown formula '{formula}'. Choose from: {self.FORMULAS}")
        self.formula = formula

    def score(self, executions: List[Execution]) -> Dict[str, float]:
        """Compute suspiciousness scores for all components.

        Args:
            executions: List of Execution objects.

        Returns:
            Dict mapping component name to suspiciousness score (0.0 to 1.0).
        """
        if not executions:
            return {}

        n_f = sum(1 for e in executions if e.is_failing)
        n_p = sum(1 for e in executions if not e.is_failing)

        components = set()
        for e in executions:
            for c in e.components:
                components.add(c)

        scores = {}
        for comp in components:
            n_ef = sum(1 for e in executions if e.is_failing and comp in e.components)
            n_ep = sum(1 for e in executions if not e.is_failing and comp in e.components)
            n_e = n_ef + n_ep

            if self.formula == "ochiai":
                scores[comp] = self._ochiai(n_ef, n_f, n_e)
            elif self.formula == "tarantula":
                scores[comp] = self._tarantula(n_ef, n_f, n_ep, n_p)
            elif self.formula == "jaccard":
                scores[comp] = self._jaccard(n_ef, n_f, n_ep)
            elif self.formula == "dstar":
                n_nf = n_f - n_ef
                scores[comp] = self._dstar(n_ef, n_ep, n_nf)

        return scores

    def rank(self, executions: List[Execution]) -> List[Tuple[str, float]]:
        """Compute scores and return components sorted by suspiciousness descending."""
        scores = self.score(executions)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    @staticmethod
    def _ochiai(n_ef: int, n_f: int, n_e: int) -> float:
        if n_f == 0 or n_e == 0:
            return 0.0
        return n_ef / (n_f * n_e) ** 0.5

    @staticmethod
    def _tarantula(n_ef: int, n_f: int, n_ep: int, n_p: int) -> float:
        denom = (n_ef / n_f) + (n_ep / n_p) if n_f > 0 and n_p > 0 else 0.0
        if denom == 0.0:
            return 0.0
        return (n_ef / n_f) / denom

    @staticmethod
    def _jaccard(n_ef: int, n_f: int, n_ep: int) -> float:
        denom = n_f + n_ep
        if denom == 0:
            return 0.0
        return n_ef / denom

    @staticmethod
    def _dstar(n_ef: int, n_ep: int, n_nf: int) -> float:
        denom = n_ep + n_nf
        if denom == 0 or n_ef == 0:
            return 0.0
        return (n_ef * n_ef) / denom
