"""Provider factory for literature backends."""
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    if backend == "ncbi":
        from bgclens.literature.providers.ncbi import NCBIProvider
        return NCBIProvider()
    if backend == "biorxiv":
        from bgclens.literature.providers.biorxiv import BioRxivProvider
        return BioRxivProvider()
    return None


def search_all(query: str, max_results: int = 24, per_source: int = 8) -> list[dict]:
    """Search EuropePMC, NCBI PubMed, and bioRxiv in parallel.

    Returns up to `per_source` results per source (deduplicated within each source),
    then cross-source deduplication by DOI/title. Total capped at max_results.
    Each result dict: title, authors, year, doi, url, abstract, source.
    """
    from bgclens.literature.providers.europepmc import _search_works, _to_citation as _epmc_to_citation
    from bgclens.literature.providers.ncbi import search_pubmed
    from bgclens.literature.providers.biorxiv import search_biorxiv

    def _fetch_europepmc():
        works = _search_works(query, per_page=per_source + 2)
        return [_epmc_to_citation(w) for w in works[:per_source]], "europepmc"

    def _fetch_pubmed():
        return search_pubmed(query, max_results=per_source), "pubmed"

    def _fetch_biorxiv():
        return search_biorxiv(query, max_results=per_source), "biorxiv"

    # Run all three providers in parallel, preserve source order for grouping
    source_buckets: dict[str, list] = {"europepmc": [], "pubmed": [], "biorxiv": []}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_fetch_europepmc): "europepmc",
            executor.submit(_fetch_pubmed): "pubmed",
            executor.submit(_fetch_biorxiv): "biorxiv",
        }
        for future in as_completed(futures):
            try:
                citations, source = future.result()
                source_buckets[source] = citations
            except Exception:
                pass

    # Cross-source deduplication — emit in source order so grouping is stable
    seen_dois: set[str] = set()
    seen_titles: set[str] = set()
    deduped: list[dict] = []

    for source in ("europepmc", "pubmed", "biorxiv"):
        for citation in source_buckets[source]:
            doi_key = (citation.doi or "").strip().lower()
            title_key = _normalize_title(citation.title)
            if doi_key and doi_key in seen_dois:
                continue
            if title_key and title_key in seen_titles:
                continue
            if doi_key:
                seen_dois.add(doi_key)
            if title_key:
                seen_titles.add(title_key)
            url = f"https://doi.org/{citation.doi}" if citation.doi else ""
            deduped.append({
                "title": citation.title,
                "authors": citation.authors,
                "year": citation.year,
                "doi": citation.doi,
                "url": url,
                "abstract": citation.abstract_snippet,
                "source": source,
            })

    return deduped[:max_results]


def _normalize_title(title: str) -> str:
    """Lowercase, strip punctuation and accents for fuzzy deduplication."""
    if not title:
        return ""
    # Normalize unicode → ASCII-safe
    normalized = unicodedata.normalize("NFKD", title)
    ascii_str = normalized.encode("ascii", "ignore").decode("ascii")
    # Strip punctuation and collapse whitespace
    stripped = re.sub(r"[^\w\s]", "", ascii_str)
    return re.sub(r"\s+", " ", stripped).strip().lower()
