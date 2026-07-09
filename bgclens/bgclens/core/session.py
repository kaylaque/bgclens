"""In-memory session for method swapping — retains last N RunRecord objects."""
from __future__ import annotations
from collections import deque
from typing import Any


class Session:
    """Holds the loaded Project and up to max_history RunRecord dicts."""

    def __init__(self, project, max_history: int = 2):
        self.project = project
        self._history: deque[dict[str, Any]] = deque(maxlen=max_history)

    def add_result(self, run_record: dict[str, Any]) -> None:
        self._history.appendleft(run_record)

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)

    @property
    def last_result(self) -> dict[str, Any] | None:
        return self._history[0] if self._history else None
