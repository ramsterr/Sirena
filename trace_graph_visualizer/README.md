# Trace Graph Visualizer

Build service dependency graphs from Jaeger traces.

## Installation

```bash
pip install trace-graph-visualizer
# or from source
PYTHONPATH=src python -m pip install .
```

## Library API

```python
from trace_graph_visualizer import JaegerFetcher, DependencyGraphBuilder

fetcher = JaegerFetcher("http://localhost:16686")
traces = fetcher.fetch_traces(service="frontend", lookback="1h", limit=200)

builder = DependencyGraphBuilder()
graph = builder.build(traces)

print(graph.nodes())
print(graph.edges(data=True))
```

## CLI

```bash
trace-graph render --jaeger-url http://localhost:16686 --lookback 1h
trace-graph export --jaeger-url http://localhost:16686 --output graph.json
trace-graph lag-windows --jaeger-url http://localhost:16686 --output lag_windows.json
```
