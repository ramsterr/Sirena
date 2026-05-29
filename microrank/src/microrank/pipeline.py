"""MicroRank pipeline: orchestrates spectrum scoring and ranking.

Provides:
    - analyze(): single-step score + rank
    - iterative_analyze(): iterative root cause removal for multi-cause scenarios
    - compare_all(): run all formula × algorithm combinations
    - MicroRankPipeline: Jaeger-backed pipeline (fetches + classifies + scores + ranks)
"""
from copy import deepcopy
from dataclasses import dataclass, field

import networkx as nx

from spectrum_scorer.models import Execution
from spectrum_scorer.scorer import SpectrumScorer, ScoreResult
from .ranker import RootCauseRanker


@dataclass
class AnalysisResult:
    """Result of a root cause analysis run.

    Attributes:
        ranked: Ranked list of (component, score) tuples, highest first.
        formula_used: The SBFL formula used (e.g. 'ochiai').
        algorithm_used: The ranking algorithm used (e.g. 'propagation').
        component_scores: Raw spectrum scores before ranking.
        n_f: Total weight of failing executions.
        n_p: Total weight of passing executions.
    """
    ranked: list[tuple[str, float]]
    formula_used: str
    algorithm_used: str
    component_scores: dict[str, float]
    n_f: float = 0.0
    n_p: float = 0.0


def analyze(
    graph: nx.DiGraph,
    executions: list[Execution],
    formula: str = "ochiai",
    algorithm: str = "propagation",
    alpha: float = 0.30,
    edge_semantics: str = "depends-on",
    temporal_half_life: float | None = None,
) -> AnalysisResult:
    """Score executions and rank components in a single step.

    Args:
        graph: Dependency graph (depends-on semantics).
        executions: List of Execution objects.
        formula: SBFL formula (ochiai, tarantula, jaccard, dstar).
        algorithm: Ranking algorithm (propagation, pagerank, anomaly_only).
        alpha: Damping factor for PageRank (default 0.30).
        edge_semantics: 'depends-on' (default) or 'calls'.
        temporal_half_life: Half-life in seconds for temporal weighting.

    Returns:
        AnalysisResult with ranked components and metadata.
    """
    scorer = SpectrumScorer(
        formula=formula,
        temporal_half_life=temporal_half_life,
    )
    score_result = scorer.score(executions)

    ranker = RootCauseRanker(alpha=alpha, edge_semantics=edge_semantics)
    if algorithm == "propagation":
        ranked = ranker.rank_propagation(graph, score_result.scores)
    elif algorithm == "pagerank":
        ranked = ranker.rank_pagerank(graph, score_result.scores)
    elif algorithm == "anomaly_only":
        ranked = ranker.rank_anomaly_only(score_result.scores)
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    return AnalysisResult(
        ranked=ranked,
        formula_used=formula,
        algorithm_used=algorithm,
        component_scores=score_result.scores,
        n_f=score_result.n_f,
        n_p=score_result.n_p,
    )


def iterative_analyze(
    graph: nx.DiGraph,
    executions: list[Execution],
    formula: str = "ochiai",
    algorithm: str = "propagation",
    max_candidates: int = 3,
    score_threshold: float = 0.0,
    alpha: float = 0.30,
    edge_semantics: str = "depends-on",
    temporal_half_life: float | None = None,
) -> list[AnalysisResult]:
    """Find root causes iteratively, removing each after discovery.

    After finding the top candidate:
    1. Record it as a root cause with its score and sub-ranking
    2. Remove all executions containing that component (they are "explained" by it)
    3. Remove the component from the graph
    4. Re-run analysis on remaining executions + graph
    5. Stop when no failing executions remain or max_candidates is reached

    Args:
        graph: Dependency graph (depends-on semantics).
        executions: List of Execution objects.
        formula: SBFL formula.
        algorithm: Ranking algorithm.
        max_candidates: Maximum number of root causes to discover.
        score_threshold: Stop if top candidate score falls below this.
        alpha: Damping factor for PageRank.
        edge_semantics: 'depends-on' or 'calls'.
        temporal_half_life: Half-life in seconds for temporal weighting.

    Returns:
        List of AnalysisResult, one per discovered root cause (ordered by impact).
    """
    results: list[AnalysisResult] = []
    remaining_execs = list(executions)
    remaining_graph = graph.copy()

    for _ in range(max_candidates):
        if not any(ex.is_failing for ex in remaining_execs):
            break

        scorer = SpectrumScorer(
            formula=formula,
            temporal_half_life=temporal_half_life,
        )
        score_result = scorer.score(remaining_execs)
        if not score_result.scores:
            break

        ranker = RootCauseRanker(alpha=alpha, edge_semantics=edge_semantics)
        if algorithm == "propagation":
            ranked = ranker.rank_propagation(
                remaining_graph, score_result.scores)
        elif algorithm == "pagerank":
            ranked = ranker.rank_pagerank(
                remaining_graph, score_result.scores)
        else:
            ranked = ranker.rank_anomaly_only(score_result.scores)

        if not ranked:
            break

        top_name, top_score = ranked[0]
        if top_score < score_threshold:
            break

        results.append(AnalysisResult(
            ranked=ranked,
            formula_used=formula,
            algorithm_used=algorithm,
            component_scores=score_result.scores,
            n_f=score_result.n_f,
            n_p=score_result.n_p,
        ))

        remaining_execs = [
            ex for ex in remaining_execs
            if top_name not in ex.components
        ]

        if top_name in remaining_graph:
            remaining_graph.remove_node(top_name)

    return results


def compare_all(
    graph: nx.DiGraph,
    executions: list[Execution],
    alpha: float = 0.30,
    edge_semantics: str = "depends-on",
    temporal_half_life: float | None = None,
) -> dict[str, list[tuple[str, float]]]:
    """Run all formula × algorithm combinations and return comparison.

    Combines 4 formulas × (pagerank, propagation, anomaly_only) +
    graph-only methods (standard_pagerank, betweenness).

    Returns:
        Dict mapping label → ranked list. Labels follow the pattern
        '{formula}_{algorithm}' for combined methods and simple names
        for graph-only methods.
    """
    formulas = ["ochiai", "tarantula", "jaccard", "dstar"]
    results: dict[str, list[tuple[str, float]]] = {}

    for formula in formulas:
        scorer = SpectrumScorer(
            formula=formula,
            temporal_half_life=temporal_half_life,
        )
        score_result = scorer.score(executions)

        ranker = RootCauseRanker(alpha=alpha, edge_semantics=edge_semantics)

        results[f"{formula}_pagerank"] = ranker.rank_pagerank(
            graph, score_result.scores)
        results[f"{formula}_propagation"] = ranker.rank_propagation(
            graph, score_result.scores)
        results[f"{formula}_anomaly_only"] = ranker.rank_anomaly_only(
            score_result.scores)

    ranker = RootCauseRanker(alpha=alpha, edge_semantics=edge_semantics)
    results["standard_pagerank"] = ranker.rank_standard_pagerank(graph)
    results["betweenness"] = ranker.rank_betweenness(graph)

    return results


class MicroRankPipeline:
    """Phase 1 pipeline: fetch traces, build graph, classify, score, rank."""

    def __init__(
        self,
        jaeger_url: str = "http://localhost:16686",
        spectrum_formula: str = "ochiai",
        pagerank_alpha: float = 0.30,
        edge_semantics: str = "depends-on",
        temporal_half_life: float | None = None,
    ):
        self.jaeger_url = jaeger_url
        self.spectrum_formula = spectrum_formula
        self.pagerank_alpha = pagerank_alpha
        self.edge_semantics = edge_semantics
        self.temporal_half_life = temporal_half_life

    def run(
        self,
        service: str | None = None,
        baseline_window: str = "30m",
        incident_window: str = "30m",
        lookback: str = "1h",
        limit: int = 200,
        algorithm: str = "propagation",
    ) -> list[tuple[str, float]]:
        from trace_graph_visualizer.fetcher import JaegerFetcher
        from trace_graph_visualizer.graph_builder import DependencyGraphBuilder
        from .trace_classifier import TraceAnomalyClassifier, traces_to_executions

        fetcher = JaegerFetcher(self.jaeger_url)
        graph_builder = DependencyGraphBuilder()

        baseline_traces = fetcher.fetch_traces(
            service=service, lookback=baseline_window, limit=limit,
        )
        classifier = TraceAnomalyClassifier()
        classifier.learn_baseline(baseline_traces)

        incident_traces = fetcher.fetch_traces(
            service=service, lookback=incident_window, limit=limit,
        )

        anomalous, normal = classifier.split_anomalous_normal(incident_traces)

        graph = graph_builder.build(baseline_traces + incident_traces)

        executions = traces_to_executions(incident_traces, anomalous)

        scorer = SpectrumScorer(
            formula=self.spectrum_formula,
            temporal_half_life=self.temporal_half_life,
        )
        score_result = scorer.score(executions)

        ranker = RootCauseRanker(
            alpha=self.pagerank_alpha,
            edge_semantics=self.edge_semantics,
        )
        ranked = ranker.rank(graph, score_result.scores, algorithm=algorithm)
        return ranked
