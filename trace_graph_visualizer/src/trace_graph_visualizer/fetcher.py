"""Fetch traces from Jaeger API."""
import requests
from datetime import datetime
from typing import List, Optional
from .models import Trace, Span


class JaegerFetcher:
    def __init__(self, jaeger_url: str, timeout: int = 30):
        self.jaeger_url = jaeger_url.rstrip("/")
        self.timeout = timeout

    def fetch_traces(
        self,
        service: Optional[str] = None,
        lookback: str = "1h",
        limit: int = 100,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Trace]:
        params = {"lookback": lookback, "limit": limit}
        if service:
            params["service"] = service
        if start:
            params["start"] = int(start.timestamp() * 1_000_000)
        if end:
            params["end"] = int(end.timestamp() * 1_000_000)

        url = f"{self.jaeger_url}/api/traces"
        resp = requests.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        traces = []
        for trace_data in data.get("data", []):
            trace = self._parse_trace(trace_data)
            if trace:
                traces.append(trace)
        return traces

    def _parse_trace(self, trace_data: dict) -> Optional[Trace]:
        try:
            trace_id = trace_data.get("traceID", "")
            spans_data = trace_data.get("spans", [])
            processes = trace_data.get("processes", {})

            if not spans_data:
                return None

            spans = []
            for span_data in spans_data:
                process_id = span_data.get("processID", "")
                process = processes.get(process_id, {})
                service_name = process.get("serviceName", "unknown")

                span = Span(
                    trace_id=trace_id,
                    span_id=span_data.get("spanID", ""),
                    parent_id=span_data.get("parentSpanID") or None,
                    service_name=service_name,
                    operation_name=span_data.get("operationName", ""),
                    start_time=datetime.fromtimestamp(
                        span_data.get("startTime", 0) / 1_000_000
                    ),
                    duration_us=float(span_data.get("duration", 0)),
                )
                spans.append(span)

            return Trace(trace_id=trace_id, spans=spans)
        except Exception:
            return None
