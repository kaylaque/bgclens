"""Protocol for pluggable literature providers."""
from typing import Protocol, runtime_checkable
from dataclasses import dataclass, field


@dataclass
class Citation:
    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    openalex_id: str | None
    abstract_snippet: str = ""


@dataclass
class MethodLiteratureSupport:
    method_id: str
    support_level: str  # "strong" | "moderate" | "weak" | "none"
    work_count: int
    citations: list[Citation] = field(default_factory=list)
    note: str = ""  # e.g. "no literature match" or "offline fallback"


@dataclass
class LiteratureRanking:
    topic: str
    method_rankings: list[MethodLiteratureSupport]
    provider: str
    cached: bool = False
    offline: bool = False


@runtime_checkable
class LiteratureProvider(Protocol):
    def support_for(
        self,
        method_terms: list[str],
        topic_terms: list[str],
        window_years: int = 10,
        max_citations: int = 5,
    ) -> list[MethodLiteratureSupport]: ...
