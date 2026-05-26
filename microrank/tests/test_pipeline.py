"""Tests for pipeline components."""
import pytest
from microrank.trace_classifier import TraceAnomalyClassifier
from microrank.ranker import RootCauseRanker


class TestRootCauseRanker:
    def test_pagerank_with_anomaly_scores(self):
        import networkx as nx
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
        import networkx as nx
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
        import networkx as nx
        G = nx.DiGraph()
        G.add_edge("A", "B", weight=5)
        G.add_edge("B", "C", weight=5)

        scores = {"A": 0.9, "B": 0.5, "C": 0.3}
        ranker = RootCauseRanker()
        results = ranker.compare(G, scores)
        assert set(results.keys()) == {"pagerank", "betweenness", "anomaly_only"}


class TestTraceAnomalyClassifier:
    def test_classifier_with_mock_traces(self):
        from datetime import datetime
        from trace_graph_visualizer.models import Trace, Span

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
        classifier.baselines["svc"] = type("B", (), {"p95_latency_ms": 100.0})()

        t_norm = MockTrace("n1", spans_norm)
        t_anom = MockTrace("a1", spans_anom)

        assert not classifier.classify_trace(t_norm)
        assert classifier.classify_trace(t_anom)
