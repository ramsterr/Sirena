"""Tests for spectrum scoring formulas."""
import pytest
from spectrum_scorer.models import Execution
from spectrum_scorer.scorer import SpectrumScorer, ScoreResult


class TestOchiai:
    def test_standard_case(self):
        executions = [
            Execution(components=["frontend", "cart", "database"], is_failing=True),
            Execution(components=["frontend", "cart", "database"], is_failing=True),
            Execution(components=["frontend", "cart"], is_failing=False),
            Execution(components=["frontend", "cart"], is_failing=False),
        ]
        result = SpectrumScorer(formula="ochiai").score(executions)
        assert isinstance(result, ScoreResult)
        scores = result.scores
        assert abs(scores["database"] - 1.0) < 0.01
        assert abs(scores["frontend"] - 0.7071) < 0.01
        assert result.formula_used == "ochiai"

    def test_all_failing_contains_component(self):
        executions = [
            Execution(components=["svc"], is_failing=True),
            Execution(components=["svc"], is_failing=True),
        ]
        result = SpectrumScorer(formula="ochiai").score(executions)
        assert result.scores["svc"] == 1.0

    def test_component_only_in_passing(self):
        executions = [
            Execution(components=["svc"], is_failing=False),
            Execution(components=["svc"], is_failing=False),
        ]
        result = SpectrumScorer(formula="ochiai").score(executions)
        assert result.scores["svc"] == 0.0

    def test_empty_executions(self):
        result = SpectrumScorer(formula="ochiai").score([])
        assert result.scores == {}
        assert result.n_f == 0.0
        assert result.n_p == 0.0

    def test_no_failing_executions(self):
        executions = [
            Execution(components=["A", "B"], is_failing=False),
            Execution(components=["C"], is_failing=False),
        ]
        result = SpectrumScorer(formula="ochiai").score(executions)
        assert result.n_f == 0.0
        for v in result.scores.values():
            assert v == 0.0


class TestOchiaiWalkThrough:
    def test_spec_example(self):
        executions = []
        for _ in range(19):
            executions.append(Execution(
                components=["frontend", "inventory-service"],
                is_failing=True,
            ))
        for _ in range(5):
            executions.append(Execution(
                components=["frontend", "inventory-service"],
                is_failing=False,
            ))
        for _ in range(1):
            executions.append(Execution(
                components=["frontend"],
                is_failing=True,
            ))
        for _ in range(75):
            executions.append(Execution(
                components=["frontend"],
                is_failing=False,
            ))

        result = SpectrumScorer(formula="ochiai").score(executions)
        assert abs(result.scores["inventory-service"] - 0.868) < 0.02
        assert abs(result.scores["frontend"] - 0.447) < 0.02


class TestTarantula:
    def test_standard_case(self):
        executions = [
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A"], is_failing=False),
            Execution(components=["A"], is_failing=False),
        ]
        result = SpectrumScorer(formula="tarantula").score(executions)
        scores = result.scores
        assert abs(scores["B"] - 1.0) < 0.01
        assert abs(scores["A"] - 0.5) < 0.01

    def test_denominator_zero(self):
        executions = [
            Execution(components=["X"], is_failing=False),
            Execution(components=["Y"], is_failing=True),
        ]
        result = SpectrumScorer(formula="tarantula").score(executions)
        assert result.scores["X"] == 0.0


class TestJaccard:
    def test_all_failing(self):
        executions = [
            Execution(components=["svc"], is_failing=True),
            Execution(components=["svc"], is_failing=True),
        ]
        result = SpectrumScorer(formula="jaccard").score(executions)
        assert result.scores["svc"] == 1.0


class TestDStar:
    def test_high_n_ef_low_n_ep(self):
        executions = [
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A", "B"], is_failing=False),
            Execution(components=["B"], is_failing=False),
        ]
        result = SpectrumScorer(formula="dstar").score(executions)
        assert result.scores["A"] > result.scores["B"]

    def test_all_failing_no_passing(self):
        executions = [
            Execution(components=["svc"], is_failing=True),
            Execution(components=["svc"], is_failing=True),
            Execution(components=["svc"], is_failing=True),
        ]
        result = SpectrumScorer(formula="dstar").score(executions)
        assert result.scores["svc"] == 9.0


class TestTemporalWeighting:
    def test_earlier_failures_weighted_higher(self):
        executions = [
            Execution(components=["A"], is_failing=True, timestamp=0.0),
            Execution(components=["B"], is_failing=True, timestamp=100.0),
        ]
        scorer = SpectrumScorer(formula="ochiai", temporal_half_life=50)
        result = scorer.score(executions)
        assert result.scores["A"] > result.scores["B"]

    def test_fallback_with_missing_timestamps(self):
        executions = [
            Execution(components=["A"], is_failing=True, timestamp=0.0),
            Execution(components=["B"], is_failing=True, timestamp=None),
        ]
        scorer = SpectrumScorer(formula="ochiai", temporal_half_life=50)
        result = scorer.score(executions)
        assert not result.temporal

    def test_all_same_timestamp(self):
        executions = [
            Execution(components=["A"], is_failing=True, timestamp=10.0),
            Execution(components=["B"], is_failing=True, timestamp=10.0),
        ]
        scorer = SpectrumScorer(formula="ochiai", temporal_half_life=50)
        result = scorer.score(executions)
        assert result.scores["A"] == result.scores["B"]


class TestScoreResult:
    def test_metadata(self):
        executions = [
            Execution(components=["A"], is_failing=True),
            Execution(components=["A"], is_failing=False),
            Execution(components=["A"], is_failing=False),
        ]
        result = SpectrumScorer(formula="ochiai").score(executions)
        assert result.formula_used == "ochiai"
        assert result.n_f == 1.0
        assert result.n_p == 2.0
        assert not result.temporal


class TestRank:
    def test_rank_sorted_descending(self):
        executions = [
            Execution(components=["high"], is_failing=True),
            Execution(components=["high"], is_failing=True),
            Execution(components=["low"], is_failing=True),
            Execution(components=["low"], is_failing=True),
        ]
        ranked = SpectrumScorer(formula="ochiai").rank(executions)
        assert ranked[0][0] == "high"
        assert ranked[1][0] == "low"
        assert ranked[0][1] >= ranked[1][1]
