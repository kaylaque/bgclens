"""MIBiG literature provider — BGC reference cluster lookup."""
import httpx
from bgclens.literature.provider import Citation, MethodLiteratureSupport, LiteratureProvider
from bgclens.literature import cache as _cache

_BASE = "https://mibig.secondarymetabolites.org/api/v1"
_TIMEOUT = 10.0


class MIBiGProvider:
    """LiteratureProvider backed by MIBiG API.

    Maps method terms to BGC compound classes and returns reference cluster citations.
    Useful for novelty/precedent queries about known BGC types.
    """

    def support_for(
        self,
        method_terms: list[str],
        topic_terms: list[str],
        window_years: int = 10,
        max_citations: int = 5,
    ) -> list[MethodLiteratureSupport]:
        results = []
        for method_term in method_terms:
            key = _cache.cache_key([f"mibig:{method_term}"], topic_terms, window_years)
            cached = _cache.get_cached(key)
            if cached is not None:
                results.append(MethodLiteratureSupport(**cached))
                continue

            # Search MIBiG for entries related to topic terms (BGC class/compound)
            compounds = topic_terms[:3]
            citations = []
            for compound in compounds:
                entries = _search_mibig(compound, max_results=max_citations)
                for entry in entries:
                    cit = _entry_to_citation(entry)
                    if cit:
                        citations.append(cit)
                if len(citations) >= max_citations:
                    break
            citations = citations[:max_citations]

            support = MethodLiteratureSupport(
                method_id=method_term,
                support_level=_support_level(len(citations)),
                work_count=len(citations),
                citations=citations,
                note="" if citations else "No MIBiG entries found for topic",
            )
            _cache.set_cached(key, support.__dict__)
            results.append(support)
        return results


def _search_mibig(query: str, max_results: int = 5) -> list[dict]:
    """Search MIBiG by compound/class name."""
    try:
        r = httpx.get(
            f"{_BASE}/entries",
            params={"query": query, "limit": max_results},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        # MIBiG API returns {"entries": [...]} or a list
        if isinstance(data, dict):
            return data.get("entries", [])
        return data[:max_results] if isinstance(data, list) else []
    except Exception:
        return []


def _entry_to_citation(entry: dict) -> Citation | None:
    """Convert a MIBiG entry dict to a Citation."""
    cluster = entry.get("cluster", entry)
    mibig_accession = entry.get("accession") or cluster.get("mibig_accession")
    compounds = cluster.get("compounds", [])
    compound_names = [c.get("compound", "") for c in compounds[:2] if c.get("compound")]
    title = (
        f"MIBiG {mibig_accession}: {', '.join(compound_names)}"
        if compound_names
        else f"MIBiG {mibig_accession}"
    )

    publications = cluster.get("publications", [])
    doi = None
    for pub in publications:
        pid = pub if isinstance(pub, str) else pub.get("pubmed_id") or pub.get("doi")
        if pid and pid.startswith("10."):
            doi = pid
            break

    if not mibig_accession:
        return None
    return Citation(
        title=title,
        authors=[],
        year=None,
        doi=doi,
        openalex_id=None,
        abstract_snippet=f"BGC class: {cluster.get('biosyn_class', [])}",
    )


def _support_level(count: int) -> str:
    if count >= 10:
        return "strong"
    if count >= 3:
        return "moderate"
    if count >= 1:
        return "weak"
    return "none"
