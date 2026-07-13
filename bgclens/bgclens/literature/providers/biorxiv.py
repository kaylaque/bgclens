"""bioRxiv / preprint provider via EuropePMC (SRC:PPR filter)."""
import time
import httpx
from bgclens.literature.provider import Citation, MethodLiteratureSupport
from bgclens.literature import cache as _cache

_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_RATE_LIMIT_SLEEP = 0.2
_TIMEOUT = 10.0


class BioRxivProvider:
    """LiteratureProvider for preprints (bioRxiv, medRxiv, etc.) via EuropePMC SRC:PPR filter."""

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

            time.sleep(_RATE_LIMIT_SLEEP)
            quoted_topics = " OR ".join('"' + t + '"' for t in topic_terms[:5])
            query = f'"{method_term}" AND ({quoted_topics})'
            citations = search_biorxiv(query, max_results=max_citations + 2)

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
                note="" if validated else "No co-occurring preprints found via EuropePMC",
            )
            _cache.set_cached(key, support.__dict__)
            results.append(support)
        return results


def search_biorxiv(query: str, max_results: int = 8) -> list[Citation]:
    """Search bioRxiv/medRxiv preprints via EuropePMC (SRC:PPR filter)."""
    preprint_query = f"({query}) AND SRC:PPR"
    params = {
        "query": preprint_query,
        "format": "json",
        "pageSize": max_results,
        "resultType": "core",
    }
    try:
        time.sleep(_RATE_LIMIT_SLEEP)
        r = httpx.get(_BASE, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        works = r.json().get("resultList", {}).get("result", [])
        return [_to_citation(w) for w in works]
    except Exception:
        return []


def _to_citation(w: dict) -> Citation:
    """Convert an EuropePMC result dict to a Citation."""
    authors = [
        a.get("fullName", a.get("lastName", ""))
        for a in w.get("authorList", {}).get("author", [])[:3]
    ]
    return Citation(
        title=w.get("title") or "",
        authors=authors,
        year=int(w["pubYear"]) if w.get("pubYear", "").isdigit() else None,
        doi=w.get("doi"),
        openalex_id=None,
        abstract_snippet=(w.get("abstractText") or "")[:200],
    )


def _support_level(count: int) -> str:
    if count >= 10:
        return "strong"
    if count >= 3:
        return "moderate"
    if count >= 1:
        return "weak"
    return "none"
