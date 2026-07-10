"""Provider factory for literature backends."""
import os
from bgclens.literature.provider import LiteratureProvider


def get_provider(name: str | None = None) -> LiteratureProvider | None:
    """Return a LiteratureProvider by name (or from BGCLENS_LITERATURE_PROVIDER env var).
    Returns None for unknown/unset → triggers offline fallback in ranker.
    """
    backend = (name or os.environ.get("BGCLENS_LITERATURE_PROVIDER", "openalex")).lower()
    if backend == "openalex":
        from bgclens.literature.providers.openalex import OpenAlexProvider
        return OpenAlexProvider()
    if backend == "europepmc":
        from bgclens.literature.providers.europepmc import EuropePMCProvider
        return EuropePMCProvider()
    if backend == "mibig":
        from bgclens.literature.providers.mibig import MIBiGProvider
        return MIBiGProvider()
    return None
