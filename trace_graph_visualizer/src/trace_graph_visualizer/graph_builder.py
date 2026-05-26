"""Build a service dependency graph from traces."""
import networkx as nx
from typing import List, Dict, Tuple
from collections import defaultdict
from .models import Trace, Span


class DependencyGraphBuilder:
    def build(self, traces: List[Trace]) -> nx.DiGraph:
        edge_durations: Dict[Tuple[str, str], List[float]] = defaultdict(list)

        for trace in traces:
            span_map = {s.span_id: s for s in trace.spans}
            for span in trace.spans:
                if span.parent_id and span.parent_id in span_map:
                    parent = span_map[span.parent_id]
                    if parent.service_name != span.service_name:
                        edge_durations[(parent.service_name, span.service_name)].append(
                            span.duration_ms
                        )

        G = nx.DiGraph()
        for (caller, callee), durations in edge_durations.items():
            G.add_edge(caller, callee, weight=len(durations), durations=durations)

        G.graph["edge_durations"] = edge_durations
        return G

    def build_with_lag_windows(
        self, graph: nx.DiGraph
    ) -> Dict[Tuple[str, str], float]:
        import numpy as np
        edge_durations = graph.graph.get("edge_durations", {})
        lag_windows = {}
        for (u, v), durations in edge_durations.items():
            if durations:
                p99 = np.percentile(durations, 99)
                lag_minutes = max(1.0, min(30.0, p99 / 1000 / 60 * 10))
            else:
                lag_minutes = 10.0
            lag_windows[(u, v)] = lag_minutes
        return lag_windows
