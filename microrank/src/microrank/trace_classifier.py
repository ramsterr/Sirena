"""Trace anomaly classifier using baseline P95 latency comparison.

A trace is anomalous if any span's duration exceeds 2x the baseline P95
latency for that service.
"""
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict

from spectrum_scorer.models import Execution


@dataclass
class ServiceBaseline:
    p95_latency_ms: float


class TraceAnomalyClassifier:
    def __init__(self, baseline_percentile: float = 95, anomaly_multiplier: float = 2.0):
        self.baseline_percentile = baseline_percentile
        self.anomaly_multiplier = anomaly_multiplier
        self.baselines: Dict[str, ServiceBaseline] = {}

    def learn_baseline(self, traces: List, min_samples: int = 50):
        service_latencies: Dict[str, List[float]] = defaultdict(list)
        for trace in traces:
            for span in trace.spans:
                service_latencies[span.service_name].append(span.duration_ms)

        for svc, latencies in service_latencies.items():
            if len(latencies) >= min_samples:
                sorted_lat = sorted(latencies)
                idx = int(len(sorted_lat) * (self.baseline_percentile / 100))
                self.baselines[svc] = ServiceBaseline(p95_latency_ms=sorted_lat[idx])

    def classify_trace(self, trace) -> bool:
        for span in trace.spans:
            baseline = self.baselines.get(span.service_name)
            if baseline and span.duration_ms > baseline.p95_latency_ms * self.anomaly_multiplier:
                return True
        return False

    def split_anomalous_normal(self, traces: List) -> Tuple[List, List]:
        anomalous = []
        normal = []
        for trace in traces:
            if self.classify_trace(trace):
                anomalous.append(trace)
            else:
                normal.append(trace)
        return anomalous, normal


def traces_to_executions(traces: List, anomalous: List) -> List[Execution]:
    anomalous_trace_ids = {t.trace_id for t in anomalous}
    executions = []
    for trace in traces:
        executions.append(Execution(
            components=trace.service_names(),
            is_failing=trace.trace_id in anomalous_trace_ids,
        ))
    return executions
