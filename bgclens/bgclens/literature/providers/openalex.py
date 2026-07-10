"""OpenAlex literature provider."""
import time
from datetime import datetime
from typing import Any
import httpx

from bgclens.literature.provider import Citation, MethodLiteratureSupport, LiteratureProvider
from bgclens.literature import cache as _cache

_BASE = "https://api.openalex.org"
_HEADERS = {"User-Agent": "BGCLens/0.1 (mailto:bgclens@example.org)"}
_RATE_LIMIT_SLEEP = 0.12   # ~8 req/s polite limit
_TIMEOUT = 10.0


def _search_works(query: str, filter_str: str = "", per_page: int = 10, window_years: int = 10) -> list[dict]:
    """Call OpenAlex /works endpoint. Returns list of work dicts."""
    params: dict[str, Any] = {
        "search": query,
        "per-page": per_page,
        "select": "id,doi,title,authorships,publication_year,abstract_inverted_index,concepts",
    }
    if filter_str:
        params["filter"] = filter_str
    elif window_years:
        from_year = datetime.now().year - window_years
        params["filter"] = f"publication_year:>{from_year}"
    try:
        r = httpx.get(f"{_BASE}/works", params=params, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception:
        return []


def _abstract_from_inverted(inverted: dict | None) -> str:
    if not inverted:
        return ""
    pairs = [(word, pos) for word, positions in inverted.items() for pos in positions]
    pairs.sort(key=lambda x: x[1])
    return " ".join(w for w, _ in pairs[:200])


def _to_citation(work: dict) -> Citation:
    authors = [
        a.get("author", {}).get("display_name", "")
        for a in work.get("authorships", [])[:3]
    ]
    return Citation(
        title=work.get("title") or "",
        authors=authors,
        year=work.get("publication_year"),
        doi=work.get("doi"),
        openalex_id=work.get("id"),
        abstract_snippet=_abstract_from_inverted(work.get("abstract_inverted_index"))[:200],
    )


def _cooccurrence_query(method_term: str, topic_terms: list[str]) -> str:
    """Build a query string requiring both method and topic."""
    topic_part = " OR ".join(f'"{t}"' for t in topic_terms[:5])
    return f'"{method_term}" AND ({topic_part})'


def _support_level(count: int) -> str:
    if count >= 10:
        return "strong"
    if count >= 3:
        return "moderate"
    if count >= 1:
        return "weak"
    return "none"


class OpenAlexProvider:
    """LiteratureProvider backed by OpenAlex REST API."""

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
            query = _cooccurrence_query(method_term, topic_terms)
            works = _search_works(query, per_page=max_citations + 2, window_years=window_years)

            # Validate co-occurrence: work must mention method term AND a topic term
            validated = []
            for w in works:
                abstract = _abstract_from_inverted(w.get("abstract_inverted_index"))
                title = (w.get("title") or "").lower()
                text = (title + " " + abstract).lower()
                m_hit = method_term.lower() in text
                t_hit = any(t.lower() in text for t in topic_terms)
                if m_hit and t_hit:
                    validated.append(_to_citation(w))
                if len(validated) >= max_citations:
                    break

            support = MethodLiteratureSupport(
                method_id=method_term,
                support_level=_support_level(len(validated)),
                work_count=len(validated),
                citations=validated,
                note="" if validated else "No co-occurring works found in OpenAlex",
            )
            _cache.set_cached(key, support.__dict__, ttl_days=7)
            results.append(support)
        return results
