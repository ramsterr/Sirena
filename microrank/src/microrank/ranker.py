"""Root cause ranker using Personalized PageRank."""
import networkx as nx
from typing import Dict, List, Tuple


class RootCauseRanker:
    ALGORITHMS = {"pagerank", "betweenness", "anomaly_only"}

    def __init__(self, alpha: float = 0.85):
        self.alpha = alpha

    def rank(
        self,
        graph: nx.DiGraph,
        anomaly_scores: Dict[str, float],
        algorithm: str = "pagerank",
    ) -> List[Tuple[str, float]]:
        if algorithm == "pagerank":
            return self._rank_pagerank(graph, anomaly_scores)
        elif algorithm == "betweenness":
            return self._rank_betweenness(graph)
        elif algorithm == "anomaly_only":
            return self._rank_anomaly_only(anomaly_scores)
        else:
            raise ValueError(f"Unknown algorithm '{algorithm}'. Choose from {self.ALGORITHMS}")

    def _rank_pagerank(
        self, graph: nx.DiGraph, anomaly_scores: Dict[str, float]
    ) -> List[Tuple[str, float]]:
        total = sum(anomaly_scores.values())
        if total == 0:
            personalization = None
        else:
            personalization = {
                node: anomaly_scores.get(node, 0.0) / total
                for node in graph.nodes()
            }

        ranked = nx.pagerank(
            graph,
            alpha=self.alpha,
            personalization=personalization,
            weight="weight",
            max_iter=100,
            tol=1e-6,
        )
        return sorted(ranked.items(), key=lambda x: x[1], reverse=True)

    def _rank_betweenness(self, graph: nx.DiGraph) -> List[Tuple[str, float]]:
        scores = nx.betweenness_centrality(graph, weight="weight")
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def _rank_anomaly_only(
        self, anomaly_scores: Dict[str, float]
    ) -> List[Tuple[str, float]]:
        return sorted(anomaly_scores.items(), key=lambda x: x[1], reverse=True)

    def compare(
        self, graph: nx.DiGraph, anomaly_scores: Dict[str, float]
    ) -> Dict[str, List[Tuple[str, float]]]:
        results = {}
        for algo in self.ALGORITHMS:
            results[algo] = self.rank(graph, anomaly_scores, algorithm=algo)
        return results
