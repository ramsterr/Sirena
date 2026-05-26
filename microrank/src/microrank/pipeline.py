"""Phase 1 pipeline: fetch traces, build graph, classify anomalies, score, and rank."""
from typing import List, Tuple, Optional
from datetime import datetime

from trace_graph_visualizer.fetcher import JaegerFetcher
from trace_graph_visualizer.graph_builder import DependencyGraphBuilder
from spectrum_scorer.models import Execution
from spectrum_scorer.scorer import SpectrumScorer
from .trace_classifier import TraceAnomalyClassifier, traces_to_executions
from .ranker import RootCauseRanker


class MicroRankPipeline:
    def __init__(
        self,
        jaeger_url: str = "http://localhost:16686",
        spectrum_formula: str = "ochiai",
        pagerank_alpha: float = 0.85,
    ):
        self.jaeger_url = jaeger_url
        self.spectrum_formula = spectrum_formula
        self.pagerank_alpha = pagerank_alpha
        self.fetcher = JaegerFetcher(jaeger_url)
        self.graph_builder = DependencyGraphBuilder()
        self.scorer = SpectrumScorer(formula=spectrum_formula)
        self.ranker = RootCauseRanker(alpha=pagerank_alpha)

    def run(
        self,
        service: Optional[str] = None,
        baseline_window: str = "30m",
        incident_window: str = "30m",
        incident_time: Optional[datetime] = None,
        lookback: str = "1h",
        limit: int = 200,
        algorithm: str = "pagerank",
    ) -> List[Tuple[str, float]]:
        baseline_traces = self.fetcher.fetch_traces(
            service=service, lookback=baseline_window, limit=limit
        )
        classifier = TraceAnomalyClassifier()
        classifier.learn_baseline(baseline_traces)

        incident_traces = self.fetcher.fetch_traces(
            service=service, lookback=incident_window, limit=limit
        )

        anomalous, normal = classifier.split_anomalous_normal(incident_traces)

        graph = self.graph_builder.build(baseline_traces + incident_traces)

        executions = traces_to_executions(incident_traces, anomalous)
        spectrum_scores = self.scorer.score(executions)

        ranked = self.ranker.rank(graph, spectrum_scores, algorithm=algorithm)
        return ranked
