"""Confidence banding thresholds."""
from typing import Literal

ConfidenceBand = Literal["green", "amber", "red"]

_GREEN_THRESHOLD = 0.8
_AMBER_THRESHOLD = 0.5


def band(passed: int, total: int) -> ConfidenceBand:
    """Return green/amber/red based on fraction of checks passed."""
    if total == 0:
        return "amber"
    ratio = passed / total
    if ratio >= _GREEN_THRESHOLD:
        return "green"
    if ratio >= _AMBER_THRESHOLD:
        return "amber"
    return "red"
