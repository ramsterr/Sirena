"""Tests for spectrum scoring formulas."""
import pytest
from spectrum_scorer.models import Execution
from spectrum_scorer.scorer import SpectrumScorer


class TestOchiai:
    def test_standard_case(self):
        executions = [
            Execution(components=["frontend", "cart", "database"], is_failing=True),
            Execution(components=["frontend", "cart", "database"], is_failing=True),
            Execution(components=["frontend", "cart"], is_failing=False),
            Execution(components=["frontend", "cart"], is_failing=False),
        ]
        scores = SpectrumScorer(formula="ochiai").score(executions)
        assert abs(scores["database"] - 1.0) < 0.01
        assert abs(scores["frontend"] - 0.7071) < 0.01

    def test_all_failing_contains_component(self):
        executions = [
            Execution(components=["svc"], is_failing=True),
            Execution(components=["svc"], is_failing=True),
        ]
        assert SpectrumScorer(formula="ochiai").score(executions)["svc"] == 1.0

    def test_component_only_in_passing(self):
        executions = [
            Execution(components=["svc"], is_failing=False),
            Execution(components=["svc"], is_failing=False),
        ]
        assert SpectrumScorer(formula="ochiai").score(executions)["svc"] == 0.0

    def test_empty_executions(self):
        assert SpectrumScorer(formula="ochiai").score([]) == {}


class TestTarantula:
    def test_standard_case(self):
        executions = [
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A"], is_failing=False),
            Execution(components=["A"], is_failing=False),
        ]
        scores = SpectrumScorer(formula="tarantula").score(executions)
        assert abs(scores["B"] - 1.0) < 0.01
        assert abs(scores["A"] - 0.5) < 0.01


class TestJaccard:
    def test_all_failing(self):
        executions = [
            Execution(components=["svc"], is_failing=True),
            Execution(components=["svc"], is_failing=True),
        ]
        assert SpectrumScorer(formula="jaccard").score(executions)["svc"] == 1.0


class TestDStar:
    def test_high_n_ef_low_n_ep(self):
        executions = [
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A", "B"], is_failing=False),
            Execution(components=["B"], is_failing=False),
        ]
        scores = SpectrumScorer(formula="dstar").score(executions)
        assert scores["A"] > scores["B"]


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
