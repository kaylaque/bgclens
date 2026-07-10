"""Rank methods by literature support for a given topic."""
from bgclens.literature.provider import (
    LiteratureProvider,
    LiteratureRanking,
    MethodLiteratureSupport,
)

_LEVEL_ORDER = {"strong": 0, "moderate": 1, "weak": 2, "none": 3}


def rank_methods(
    method_ids: list[str],
    method_display_names: dict[str, str],
    topic: str,
    provider: LiteratureProvider | None,
    window_years: int = 10,
) -> LiteratureRanking:
    """
    Query provider for each method × topic, validate co-occurrence, return ranked list.
    Falls back gracefully if provider is None or raises.
    """
    topic_terms = _topic_to_terms(topic)

    if provider is None:
        return _offline_fallback(method_ids, topic)

    try:
        # Use display names as search terms (more precise than IDs)
        method_terms = [method_display_names.get(mid, mid) for mid in method_ids]
        supports = provider.support_for(
            method_terms=method_terms,
            topic_terms=topic_terms,
            window_years=window_years,
        )
        # Re-attach method_ids
        for i, s in enumerate(supports):
            s.method_id = method_ids[i]
    except Exception as e:
        return _offline_fallback(method_ids, topic, note=f"Provider error: {e}")

    # Sort by support level
    supports.sort(key=lambda s: (_LEVEL_ORDER.get(s.support_level, 99), -s.work_count))

    return LiteratureRanking(
        topic=topic,
        method_rankings=supports,
        provider="openalex",
    )


def _topic_to_terms(topic: str) -> list[str]:
    """Extract search terms from free-text topic."""
    stopwords = {"the", "a", "an", "of", "for", "in", "and", "or", "vs", "between", "with"}
    words = [w.strip("?,. ") for w in topic.lower().split() if len(w) > 3]
    return [w for w in words if w not in stopwords][:5] or [topic[:40]]


def _offline_fallback(
    method_ids: list[str], topic: str, note: str = ""
) -> LiteratureRanking:
    supports = [
        MethodLiteratureSupport(
            method_id=mid,
            support_level="none",
            work_count=0,
            citations=[],
            note="No literature ranking (offline)" + (f" — {note}" if note else ""),
        )
        for mid in method_ids
    ]
    return LiteratureRanking(
        topic=topic,
        method_rankings=supports,
        provider="offline",
        offline=True,
    )


def _dedup_citations(citations: list) -> list:
    """Deduplicate citations by DOI (or title as fallback)."""
    seen_keys: set[str] = set()
    result = []
    for c in citations:
        key = c.doi or c.title
        if key and key not in seen_keys:
            seen_keys.add(key)
            result.append(c)
    return result


def merge_supports(
    supports_list: list[list[MethodLiteratureSupport]],
    method_ids: list[str],
) -> list[MethodLiteratureSupport]:
    """Merge support lists from multiple providers: take max support_level, combine citations."""
    merged: dict[str, MethodLiteratureSupport] = {}
    _order = {"strong": 0, "moderate": 1, "weak": 2, "none": 3}
    for supports in supports_list:
        for s in supports:
            if s.method_id not in merged:
                merged[s.method_id] = s
            else:
                existing = merged[s.method_id]
                # take the better support level
                if _order.get(s.support_level, 99) < _order.get(existing.support_level, 99):
                    deduped = _dedup_citations(existing.citations + s.citations)
                    merged[s.method_id] = MethodLiteratureSupport(
                        method_id=s.method_id,
                        support_level=s.support_level,
                        work_count=len(deduped),
                        citations=deduped,
                        note=f"merged from {len(supports_list)} providers",
                    )
                else:
                    existing.citations = _dedup_citations(existing.citations + s.citations)
                    existing.work_count = len(existing.citations)
    return [
        merged.get(mid, MethodLiteratureSupport(method_id=mid, support_level="none", work_count=0))
        for mid in method_ids
    ]
