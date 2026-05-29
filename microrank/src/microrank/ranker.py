"""Root cause ranker using Personalized PageRank, Upstream Propagation,
Betweenness Centrality, Standard PageRank, and Anomaly-Only ranking."""
import networkx as nx


class RootCauseRanker:
    """Implements five ranking algorithms for root cause analysis.

    Algorithms:
        - pagerank: Personalized PageRank with anomaly scores as personalization
        - propagation: Upstream anomaly propagation along dependency edges
        - standard_pagerank: Standard PageRank (uniform personalization)
        - betweenness: Betweenness centrality (structural importance)
        - anomaly_only: Rank by anomaly score alone (no graph structure)

    Edge semantics:
        Default is "depends-on" (B→A means B depends on A). Set
        edge_semantics="calls" if edges mean "A calls B" — the ranker
        auto-reverses edges so PageRank correctly amplifies root causes
        (upstream dependencies) instead of victims (downstream sinks).
    """

    ALGORITHMS = {
        "pagerank", "propagation", "standard_pagerank",
        "betweenness", "anomaly_only",
    }

    def __init__(self, alpha: float = 0.30,
                 edge_semantics: str = "depends-on"):
        self.alpha = alpha
        if edge_semantics not in ("depends-on", "calls"):
            raise ValueError(
                f"edge_semantics must be 'depends-on' or 'calls', "
                f"got '{edge_semantics}'"
            )
        self.edge_semantics = edge_semantics

    def rank(
        self,
        graph: nx.DiGraph,
        anomaly_scores: dict[str, float],
        algorithm: str = "propagation",
    ) -> list[tuple[str, float]]:
        if algorithm == "pagerank":
            return self.rank_pagerank(graph, anomaly_scores)
        elif algorithm == "propagation":
            return self.rank_propagation(graph, anomaly_scores)
        elif algorithm == "standard_pagerank":
            return self.rank_standard_pagerank(graph)
        elif algorithm == "betweenness":
            return self.rank_betweenness(graph)
        elif algorithm == "anomaly_only":
            return self.rank_anomaly_only(anomaly_scores)
        else:
            raise ValueError(
                f"Unknown algorithm '{algorithm}'. "
                f"Choose from {self.ALGORITHMS}"
            )

    def _prepare_graph(self, graph: nx.DiGraph) -> nx.DiGraph:
        """Return graph with correct edge semantics for ranking.

        If edges represent "A calls B" (calls semantics), reverse them
        to "depends-on" (B depends on A) so that PageRank propagates
        rank upstream toward root causes.
        """
        if self.edge_semantics == "calls":
            return graph.reverse(copy=True)
        return graph

    def rank_pagerank(
        self,
        graph: nx.DiGraph,
        anomaly_scores: dict[str, float],
    ) -> list[tuple[str, float]]:
        """Personalized PageRank with anomaly scores as personalization.

        Args:
            graph: Dependency graph. Edges should point FROM dependent TO
                   dependency (B depends on A → edge B→A).
            anomaly_scores: Dict mapping node → suspiciousness score [0..1].
        """
        g = self._prepare_graph(graph)

        total = sum(anomaly_scores.values())
        if total == 0:
            personalization = None
        else:
            personalization = {
                node: anomaly_scores.get(node, 0.0) / total
                for node in g.nodes()
            }

        ranked = nx.pagerank(
            g,
            alpha=self.alpha,
            personalization=personalization,
            weight="weight",
            max_iter=100,
            tol=1e-6,
        )
        return sorted(ranked.items(), key=lambda x: x[1], reverse=True)

    def rank_propagation(
        self,
        graph: nx.DiGraph,
        anomaly_scores: dict[str, float],
        decay: float = 0.80,
    ) -> list[tuple[str, float]]:
        """Propagate anomaly scores upstream along dependency edges.

        If B depends on A (edge B→A) and B shows anomalies, A's score is
        partially boosted — because A's failure would cause B's symptoms.
        Uses topological order (leaves first) to propagate in one pass.
        Simpler and more interpretable than PageRank for root cause analysis.

        Args:
            graph: Dependency graph (depends-on semantics).
            anomaly_scores: Spectrum scores dict.
            decay: Fraction of downstream anomaly that propagates upstream (0..1).
        """
        g = self._prepare_graph(graph)

        scores = dict(anomaly_scores)
        try:
            order = list(nx.topological_sort(g))
        except nx.NetworkXUnfeasible:
            order = list(g.nodes())

        for node in order:
            node_score = scores.get(node, 0.0)
            for dep in g.successors(node):
                boost = node_score * decay
                if boost > scores.get(dep, 0.0):
                    scores[dep] = boost

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def rank_standard_pagerank(
        self, graph: nx.DiGraph,
    ) -> list[tuple[str, float]]:
        """Standard PageRank — uniform personalization. Useful as baseline."""
        g = self._prepare_graph(graph)
        ranked = nx.pagerank(
            g, alpha=self.alpha, weight="weight", max_iter=100,
        )
        return sorted(ranked.items(), key=lambda x: x[1], reverse=True)

    def rank_betweenness(
        self, graph: nx.DiGraph,
    ) -> list[tuple[str, float]]:
        """Betweenness centrality — structural importance only.

        Edge weights are treated as connection strength (higher = stronger).
        They are inverted to distance (1/weight) because NetworkX's
        betweenness treats weights as distances.
        """
        g = self._prepare_graph(graph)
        inverted = g.copy()
        for u, v, data in inverted.edges(data=True):
            w = data.get("weight", 1.0)
            data["distance"] = 1.0 / w if w > 0 else float("inf")
        scores = nx.betweenness_centrality(inverted, weight="distance")
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def rank_anomaly_only(
        self, anomaly_scores: dict[str, float],
    ) -> list[tuple[str, float]]:
        """Rank by anomaly score alone — no graph consideration."""
        return sorted(anomaly_scores.items(), key=lambda x: x[1], reverse=True)

    def compare(
        self, graph: nx.DiGraph, anomaly_scores: dict[str, float],
    ) -> dict[str, list[tuple[str, float]]]:
        """Run all five ranking algorithms and return results."""
        results = {}
        for algo in self.ALGORITHMS:
            results[algo] = self.rank(graph, anomaly_scores, algorithm=algo)
        return results
