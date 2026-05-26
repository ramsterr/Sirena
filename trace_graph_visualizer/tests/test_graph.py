"""Tests for trace graph visualizer."""
import pytest
from trace_graph_visualizer.models import Trace, Span
from trace_graph_visualizer.graph_builder import DependencyGraphBuilder


def make_trace(trace_id: str, spans: list) -> Trace:
    return Trace(trace_id=trace_id, spans=spans)


def make_span(span_id: str, parent_id: str, service: str, duration_ms: float) -> Span:
    from datetime import datetime
    return Span(
        trace_id="t1",
        span_id=span_id,
        parent_id=parent_id,
        service_name=service,
        operation_name="op",
        start_time=datetime.now(),
        duration_us=duration_ms * 1000,
    )


class TestDependencyGraphBuilder:
    def test_single_trace_two_services(self):
        spans = [
            make_span("s1", None, "frontend", 0),
            make_span("s2", "s1", "backend", 100),
        ]
        graph = DependencyGraphBuilder().build([make_trace("t1", spans)])
        assert "frontend" in graph.nodes()
        assert "backend" in graph.nodes()
        assert graph.has_edge("frontend", "backend")
        assert graph["frontend"]["backend"]["weight"] == 1

    def test_multiple_traces_aggregate_edge_weights(self):
        spans1 = [
            make_span("a1", None, "A", 0),
            make_span("a2", "a1", "B", 50),
        ]
        spans2 = [
            make_span("b1", None, "A", 0),
            make_span("b2", "b1", "B", 60),
        ]
        graph = DependencyGraphBuilder().build([
            make_trace("t1", spans1),
            make_trace("t2", spans2),
        ])
        assert graph["A"]["B"]["weight"] == 2

    def test_lag_windows(self):
        spans = [
            make_span("s1", None, "frontend", 0),
            make_span("s2", "s1", "backend", 6000),
        ]
        graph = DependencyGraphBuilder().build([make_trace("t1", spans)])
        lag = DependencyGraphBuilder().build_with_lag_windows(graph)
        assert ("frontend", "backend") in lag


class TestTraceModel:
    def test_service_names(self):
        spans = [
            make_span("s1", None, "frontend", 0),
            make_span("s2", "s1", "backend", 100),
            make_span("s3", "s2", "db", 50),
        ]
        trace = make_trace("t1", spans)
        assert set(trace.service_names()) == {"frontend", "backend", "db"}
