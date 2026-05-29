"""Tests for MicroRank ranker, pipeline, and classifier."""
import networkx as nx
import pytest

from microrank.ranker import RootCauseRanker
from microrank.pipeline import (
    AnalysisResult, analyze, iterative_analyze, compare_all, MicroRankPipeline,
)
from microrank.trace_classifier import TraceAnomalyClassifier


class TestRootCauseRanker:
    def test_pagerank_with_anomaly_scores(self):
        G = nx.DiGraph()
        G.add_edge("A", "B", weight=10)
        G.add_edge("B", "C", weight=10)

        anomaly_scores = {"A": 0.9, "B": 0.05, "C": 0.05}
        ranker = RootCauseRanker(alpha=0.85)
        ranked = ranker.rank(G, anomaly_scores, "pagerank")
        names = [n for n, _ in ranked]

        assert names[0] == "A"
        assert names[1] == "B"
        assert names[2] == "C"

    def test_betweenness_linear_graph(self):
        G = nx.DiGraph()
        G.add_edge("A", "B", weight=5)
        G.add_edge("B", "C", weight=5)

        ranker = RootCauseRanker()
        ranked = ranker.rank(G, {}, "betweenness")
        assert ranked[0][0] == "B"

    def test_anomaly_only_ranking(self):
        scores = {"A": 0.8, "B": 0.5, "C": 0.2}
        ranked = RootCauseRanker().rank(None, scores, "anomaly_only")
        assert ranked[0][0] == "A"
        assert ranked[0][1] == 0.8

    def test_compare_all_algorithms(self):
        G = nx.DiGraph()
        G.add_edge("A", "B", weight=5)
        G.add_edge("B", "C", weight=5)

        scores = {"A": 0.9, "B": 0.5, "C": 0.3}
        ranker = RootCauseRanker()
        results = ranker.compare(G, scores)
        expected = {"pagerank", "propagation", "standard_pagerank",
                     "betweenness", "anomaly_only"}
        assert set(results.keys()) == expected

    def test_default_alpha_is_0_30(self):
        ranker = RootCauseRanker()
        assert ranker.alpha == 0.30

    def test_propagation_upstream_boosts_dependency(self):
        G = nx.DiGraph()
        G.add_edge("A", "B", weight=10)
        G.add_edge("B", "C", weight=10)

        scores = {"A": 0.9, "B": 0.05, "C": 0.05}
        ranker = RootCauseRanker()
        ranked = ranker.rank(G, scores, "propagation")
        names = [n for n, _ in ranked]
        assert names[0] == "A"

    def test_propagation_acyclic_single_pass(self):
        G = nx.DiGraph()
        G.add_edge("frontend", "cart", weight=10)
        G.add_edge("cart", "database", weight=10)

        scores = {"frontend": 0.0, "cart": 0.9, "database": 0.0}
        ranker = RootCauseRanker()
        ranked = ranker.rank(G, scores, "propagation")
        assert ranked[0][0] == "cart"

    def test_propagation_with_cycle_fallback(self):
        G = nx.DiGraph()
        G.add_edge("A", "B", weight=10)
        G.add_edge("B", "A", weight=10)

        scores = {"A": 0.9, "B": 0.5}
        ranker = RootCauseRanker()
        ranked = ranker.rank(G, scores, "propagation")
        assert len(ranked) == 2

    def test_standard_pagerank(self):
        G = nx.DiGraph()
        G.add_edge("A", "B", weight=10)
        G.add_edge("C", "B", weight=10)

        ranker = RootCauseRanker(alpha=0.85)
        ranked = ranker.rank(G, {}, "standard_pagerank")
        assert ranked[0][0] == "B"

    def test_edge_semantics_calls_reverses(self):
        G = nx.DiGraph()
        G.add_edge("A", "B", weight=10)

        scores = {"A": 0.9, "B": 0.1}

        ranker_dep = RootCauseRanker(edge_semantics="depends-on")
        ranker_call = RootCauseRanker(edge_semantics="calls")

        ranked_dep = ranker_dep.rank(G, scores, "pagerank")
        ranked_call = ranker_call.rank(G, scores, "pagerank")
        assert ranked_dep != ranked_call

    def test_betweenness_weight_inversion(self):
        G = nx.DiGraph()
        G.add_edge("A", "B", weight=1)
        G.add_edge("A", "B", weight=100)

        ranker = RootCauseRanker()
        ranked = ranker.rank(G, {}, "betweenness")
        assert len(ranked) == 2

    def test_rank_method_fallback(self):
        G = nx.DiGraph()
        ranker = RootCauseRanker()
        with pytest.raises(ValueError, match="Unknown algorithm"):
            ranker.rank(G, {}, "nonexistent")


class TestAnalyze:
    def test_analyze_returns_analysis_result(self):
        G = nx.DiGraph()
        G.add_node("A")
        G.add_node("B")
        G.add_edge("A", "B", weight=10)

        from spectrum_scorer.models import Execution
        executions = [
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A"], is_failing=False),
        ]

        result = analyze(G, executions, formula="ochiai",
                         algorithm="propagation")
        assert isinstance(result, AnalysisResult)
        assert result.formula_used == "ochiai"
        assert result.algorithm_used == "propagation"
        assert len(result.ranked) >= 1
        assert result.n_f == 2.0
        assert result.n_p == 1.0

    def test_analyze_anomaly_only(self):
        G = nx.DiGraph()
        G.add_node("A")
        G.add_node("B")

        from spectrum_scorer.models import Execution
        executions = [
            Execution(components=["A", "B"], is_failing=True),
        ]

        result = analyze(G, executions, formula="ochiai",
                         algorithm="anomaly_only")
        assert result.algorithm_used == "anomaly_only"


class TestIterativeAnalyze:
    def test_single_root_cause_stops_after_one(self):
        G = nx.DiGraph()
        G.add_node("A")
        G.add_node("B")

        from spectrum_scorer.models import Execution
        executions = [
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A", "B"], is_failing=True),
        ]

        results = iterative_analyze(G, executions, max_candidates=3)
        assert len(results) == 1

    def test_two_independent_root_causes(self):
        G = nx.DiGraph()
        G.add_node("A")
        G.add_node("B")
        G.add_node("C")
        G.add_node("D")

        from spectrum_scorer.models import Execution
        executions = [
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["C", "D"], is_failing=True),
            Execution(components=["C", "D"], is_failing=True),
            Execution(components=["A", "C"], is_failing=False),
        ]

        results = iterative_analyze(G, executions, max_candidates=3)
        assert len(results) == 2

    def test_score_threshold_returns_empty(self):
        G = nx.DiGraph()
        G.add_node("A")

        from spectrum_scorer.models import Execution
        executions = [
            Execution(components=["A"], is_failing=True),
        ]

        results = iterative_analyze(G, executions, score_threshold=1.1)
        assert len(results) == 0

    def test_max_candidates_limits(self):
        G = nx.DiGraph()
        G.add_node("A")

        from spectrum_scorer.models import Execution
        executions = [
            Execution(components=["A"], is_failing=True),
        ]

        results = iterative_analyze(G, executions, max_candidates=1,
                                    algorithm="anomaly_only")
        assert len(results) == 1

    def test_no_failing_stops_immediately(self):
        G = nx.DiGraph()
        G.add_node("A")

        from spectrum_scorer.models import Execution
        executions = [
            Execution(components=["A"], is_failing=False),
        ]

        results = iterative_analyze(G, executions, max_candidates=5)
        assert len(results) == 0


class TestCompareAll:
    def test_returns_all_combinations(self):
        G = nx.DiGraph()
        G.add_node("A")
        G.add_node("B")
        G.add_edge("A", "B", weight=10)

        from spectrum_scorer.models import Execution
        executions = [
            Execution(components=["A", "B"], is_failing=True),
            Execution(components=["A"], is_failing=False),
        ]

        results = compare_all(G, executions)
        expected_keys = {
            "ochiai_pagerank", "ochiai_propagation", "ochiai_anomaly_only",
            "tarantula_pagerank", "tarantula_propagation", "tarantula_anomaly_only",
            "jaccard_pagerank", "jaccard_propagation", "jaccard_anomaly_only",
            "dstar_pagerank", "dstar_propagation", "dstar_anomaly_only",
            "standard_pagerank", "betweenness",
        }
        assert set(results.keys()) == expected_keys
        for ranked in results.values():
            assert len(ranked) >= 1


class TestTraceAnomalyClassifier:
    def test_classifier_with_mock_traces(self):
        class MockSpan:
            def __init__(self, svc, dur):
                self.service_name = svc
                self.duration_ms = dur

        class MockTrace:
            def __init__(self, tid, spans):
                self.trace_id = tid
                self.spans = spans

            def service_names(self):
                return sorted(set(s.service_name for s in self.spans))

        spans_norm = [MockSpan("svc", 50), MockSpan("svc", 60)]
        spans_anom = [MockSpan("svc", 500)]

        classifier = TraceAnomalyClassifier()
        classifier.baselines["svc"] = type(
            "B", (), {"p95_latency_ms": 100.0})()

        t_norm = MockTrace("n1", spans_norm)
        t_anom = MockTrace("a1", spans_anom)

        assert not classifier.classify_trace(t_norm)
        assert classifier.classify_trace(t_anom)
