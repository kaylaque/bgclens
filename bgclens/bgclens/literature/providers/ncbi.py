"""NCBI PubMed literature provider via E-utilities."""
import time
import httpx
from bgclens.literature.provider import Citation, MethodLiteratureSupport
from bgclens.literature import cache as _cache

_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_RATE_LIMIT_SLEEP = 0.35
_TIMEOUT = 12.0
_TOOL = "bgclens"
_EMAIL = "bgclens@example.com"


class NCBIProvider:
    """LiteratureProvider backed by NCBI PubMed E-utilities."""

    def support_for(
        self,
        method_terms: list[str],
        topic_terms: list[str],
        window_years: int = 10,
        max_citations: int = 5,
    ) -> list[MethodLiteratureSupport]:
        results = []
        for method_term in method_terms:
            key = _cache.cache_key([method_term], topic_terms, window_years)
            cached = _cache.get_cached(key)
            if cached is not None:
                results.append(MethodLiteratureSupport(**cached))
                continue

            quoted_topics = " OR ".join('"' + t + '"' for t in topic_terms[:5])
            query = f'"{method_term}" AND ({quoted_topics})'
            citations = search_pubmed(query, max_results=max_citations + 2)

            validated = []
            for c in citations:
                title = (c.title or "").lower()
                abstract = (c.abstract_snippet or "").lower()
                text = title + " " + abstract
                if method_term.lower() in text and any(t.lower() in text for t in topic_terms):
                    validated.append(c)
                if len(validated) >= max_citations:
                    break

            support = MethodLiteratureSupport(
                method_id=method_term,
                support_level=_support_level(len(validated)),
                work_count=len(validated),
                citations=validated,
                note="" if validated else "No co-occurring works found in NCBI PubMed",
            )
            _cache.set_cached(key, support.__dict__)
            results.append(support)
        return results


def search_pubmed(query: str, max_results: int = 8) -> list[Citation]:
    """Search PubMed via E-utilities and return a list of Citations."""
    try:
        # Step 1: esearch — get PMIDs
        time.sleep(_RATE_LIMIT_SLEEP)
        esearch_params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "tool": _TOOL,
            "email": _EMAIL,
        }
        r = httpx.get(_ESEARCH, params=esearch_params, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        pmids = data.get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return []

        # Step 2: esummary — get metadata for each PMID
        time.sleep(_RATE_LIMIT_SLEEP)
        esummary_params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json",
            "tool": _TOOL,
            "email": _EMAIL,
        }
        r2 = httpx.get(_ESUMMARY, params=esummary_params, timeout=_TIMEOUT)
        r2.raise_for_status()
        summary_data = r2.json()
        result_dict = summary_data.get("result", {})

        citations = []
        for pmid in pmids:
            item = result_dict.get(pmid)
            if not item or not isinstance(item, dict):
                continue
            citations.append(_summary_to_citation(item))
        return citations

    except Exception:
        return []


def _summary_to_citation(item: dict) -> Citation:
    """Convert an esummary result item to a Citation."""
    title = item.get("title") or ""

    # Authors: list of dicts with "name" key like "Smith J"
    raw_authors = item.get("authors", [])
    authors = [a.get("name", "") for a in raw_authors[:3] if isinstance(a, dict)]

    # Year: pubdate is a string like "2023 Jan" or "2023"
    pubdate = item.get("pubdate", "")
    year: int | None = None
    if pubdate:
        year_str = pubdate.split()[0]
        if year_str.isdigit():
            year = int(year_str)

    # DOI: in articleids list where idtype == "doi"
    doi: str | None = None
    for aid in item.get("articleids", []):
        if isinstance(aid, dict) and aid.get("idtype") == "doi":
            doi = aid.get("value") or None
            break

    return Citation(
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        openalex_id=None,
        abstract_snippet="",
    )


def _support_level(count: int) -> str:
    if count >= 10:
        return "strong"
    if count >= 3:
        return "moderate"
    if count >= 1:
        return "weak"
    return "none"
