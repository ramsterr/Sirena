"""Data models for spectrum-based fault localization."""
from dataclasses import dataclass


@dataclass
class Execution:
    """A single execution (e.g., a trace) with involved components and a pass/fail label.

    Attributes:
        components: Which components were involved in this execution.
        is_failing: Whether this execution failed.
        timestamp: Optional unix timestamp or monotonically increasing ID.
                   Used by temporal weighting — earlier timestamps get higher weight.
    """
    components: list[str]
    is_failing: bool
    timestamp: float | None = None
