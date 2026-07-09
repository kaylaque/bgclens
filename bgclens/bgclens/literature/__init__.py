"""Literature service for BGCLens."""
from bgclens.literature.provider import (
    Citation,
    LiteratureProvider,
    LiteratureRanking,
    MethodLiteratureSupport,
)
from bgclens.literature.openalex import OpenAlexProvider
from bgclens.literature.ranker import rank_methods

__all__ = [
    "Citation",
    "LiteratureProvider",
    "LiteratureRanking",
    "MethodLiteratureSupport",
    "OpenAlexProvider",
    "rank_methods",
]
