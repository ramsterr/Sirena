# MicroRank

Trace-based root cause analysis using spectrum scoring + Personalized PageRank.

## Architecture

```
Jaeger API → Trace Fetcher → Dependency Graph
                                  ↓
                    Anomaly Classifier (baseline P95)
                                  ↓
                    Spectrum Scorer (Ochiai/Tarantula/Jaccard/DStar)
                                  ↓
                    Personalized PageRank Ranker
                                  ↓
                            Ranked RCA output
```

## Installation

```bash
PYTHONPATH=src python -m pip install .
```

## CLI

```bash
micro-rank rank --jaeger-url http://localhost:16686 --service frontend --lookback 1h
micro-rank rank --jaeger-url http://localhost:16686 --algorithm pagerank --formula ochiai
micro-rank compare --jaeger-url http://localhost:16686
```

## Library API

```python
from microrank import MicroRankPipeline

pipeline = MicroRankPipeline(jaeger_url="http://localhost:16686")
ranked = pipeline.run(service="frontend", lookback="1h", limit=200)
print(ranked)
```
