"""Data models for traces from Jaeger."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Span:
    """A single span from a distributed trace."""
    trace_id: str
    span_id: str
    parent_id: Optional[str]
    service_name: str
    operation_name: str
    start_time: datetime
    duration_us: float

    @property
    def duration_ms(self) -> float:
        return self.duration_us / 1000.0


@dataclass
class Trace:
    """A complete trace (directed tree of spans) representing one request."""
    trace_id: str
    spans: List[Span] = field(default_factory=list)

    def service_names(self) -> List[str]:
        return sorted(set(s.service_name for s in self.spans))

    def get_span(self, span_id: str) -> Optional[Span]:
        return next((s for s in self.spans if s.span_id == span_id), None)
