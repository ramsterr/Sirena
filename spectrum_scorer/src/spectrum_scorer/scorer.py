"""Spectrum-based fault localization using Ochiai, Tarantula, Jaccard, and DStar."""
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from .models import Execution

logger = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    """Result of spectrum scoring with metadata.

    Attributes:
        scores: Dict mapping component name to suspiciousness score (0.0 to 1.0).
        formula_used: The scoring formula that produced these results.
        n_f: Total weight of failing executions.
        n_p: Total weight of passing executions.
        temporal: Whether temporal weighting was active.
        temporal_half_life: The half-life used, if temporal mode was active.
    """
    scores: dict[str, float]
    formula_used: str
    n_f: float
    n_p: float
    temporal: bool = False
    temporal_half_life: float | None = None


class SpectrumScorer:
    """Computes spectrum-based suspiciousness scores for components.

    Takes execution data (list of Execution objects with involved components
    and pass/fail label) and computes a suspiciousness score per component using
    a chosen spectrum formula.

    Supports optional temporal weighting: earlier executions are weighted higher
    via exponential decay, capturing anomaly-onset ordering.
    """

    FORMULAS = {"ochiai", "tarantula", "jaccard", "dstar"}

    def __init__(self, formula: str = "ochiai",
                 temporal_half_life: float | None = None):
        if formula not in self.FORMULAS:
            raise ValueError(
                f"Unknown formula '{formula}'. Choose from: {self.FORMULAS}")
        self.formula = formula
        self.temporal_half_life = temporal_half_life

    def score(self, executions: list[Execution]) -> ScoreResult:
        """Compute suspiciousness scores for all components.

        Args:
            executions: List of Execution objects. Timestamps are optional;
                used only if temporal_half_life is set and all executions
                have timestamps.

        Returns:
            ScoreResult with scores dict and metadata.
        """
        if not executions:
            return ScoreResult(
                scores={},
                formula_used=self.formula,
                n_f=0.0,
                n_p=0.0,
            )

        has_timestamps = all(ex.timestamp is not None for ex in executions)
        use_temporal = (self.temporal_half_life is not None
                        and has_timestamps)

        if self.temporal_half_life is not None and not has_timestamps:
            logger.warning(
                "temporal_half_life is set but some executions lack timestamps; "
                "falling back to uniform weighting"
            )

        if use_temporal:
            t_first = min(ex.timestamp for ex in executions)  # type: ignore[type-var]
            t_last = max(ex.timestamp for ex in executions)  # type: ignore[type-var]
            weights = {}
            for ex in executions:
                dt = ex.timestamp - t_first  # type: ignore[operator]
                if dt <= 0:
                    weights[id(ex)] = 1.0
                else:
                    weights[id(ex)] = 0.5 ** (dt / self.temporal_half_life)

        n_ef: defaultdict[str, float] = defaultdict(float)
        n_ep: defaultdict[str, float] = defaultdict(float)
        n_f: float = 0.0

        for ex in executions:
            w: float = weights[id(ex)] if use_temporal else 1.0
            if ex.is_failing:
                n_f += w
                for comp in ex.components:
                    n_ef[comp] += w
            else:
                for comp in ex.components:
                    n_ep[comp] += w

        total_weight: float
        if use_temporal:
            total_weight = sum(weights[id(ex)] for ex in executions)
        else:
            total_weight = float(len(executions))

        n_p: float = total_weight - n_f
        components: set[str] = set(n_ef.keys()) | set(n_ep.keys())

        if n_f == 0.0:
            result = {c: 0.0 for c in components}
            return ScoreResult(
                scores=dict(
                    sorted(result.items(), key=lambda x: x[1], reverse=True)),
                formula_used=self.formula,
                n_f=n_f,
                n_p=n_p,
                temporal=use_temporal,
                temporal_half_life=self.temporal_half_life,
            )

        scores: dict[str, float] = {}
        for comp in components:
            ef: float = n_ef[comp]
            ep: float = n_ep[comp]
            n_e: float = ef + ep
            n_nf: float = n_f - ef

            if n_e == 0.0:
                scores[comp] = 0.0
                continue

            if self.formula == "ochiai":
                scores[comp] = self._ochiai(ef, n_f, n_e)
            elif self.formula == "tarantula":
                scores[comp] = self._tarantula(ef, n_f, ep, n_p)
            elif self.formula == "jaccard":
                scores[comp] = self._jaccard(ef, n_f, ep)
            elif self.formula == "dstar":
                scores[comp] = self._dstar(ef, ep, n_nf)

        sorted_scores = dict(
            sorted(scores.items(), key=lambda x: x[1], reverse=True)
        )
        return ScoreResult(
            scores=sorted_scores,
            formula_used=self.formula,
            n_f=n_f,
            n_p=n_p,
            temporal=use_temporal,
            temporal_half_life=self.temporal_half_life,
        )

    def rank(self, executions: list[Execution]) -> list[tuple[str, float]]:
        """Compute scores and return components sorted by suspiciousness descending."""
        result = self.score(executions)
        return list(result.scores.items())

    @staticmethod
    def _ochiai(n_ef: float, n_f: float, n_e: float) -> float:
        if n_f == 0.0 or n_e == 0.0 or n_ef == 0.0:
            return 0.0
        denom = (n_f * n_e) ** 0.5
        return n_ef / denom if denom > 0.0 else 0.0

    @staticmethod
    def _tarantula(n_ef: float, n_f: float, n_ep: float, n_p: float) -> float:
        fail_ratio = n_ef / n_f if n_f > 0.0 else 0.0
        pass_ratio = n_ep / n_p if n_p > 0.0 else 0.0
        denom = fail_ratio + pass_ratio
        return fail_ratio / denom if denom > 0.0 else 0.0

    @staticmethod
    def _jaccard(n_ef: float, n_f: float, n_ep: float) -> float:
        denom = n_f + n_ep
        return n_ef / denom if denom > 0.0 else 0.0

    @staticmethod
    def _dstar(n_ef: float, n_ep: float, n_nf: float) -> float:
        denom = n_ep + n_nf
        if denom == 0.0:
            return float(n_ef ** 2)
        return (n_ef ** 2) / denom
