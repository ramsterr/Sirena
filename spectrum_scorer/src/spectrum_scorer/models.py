"""Data models for spectrum-based fault localization."""
from dataclasses import dataclass
from typing import List


@dataclass
class Execution:
    """A single execution (e.g., a trace) with involved components and a pass/fail label."""
    components: List[str]
    is_failing: bool
