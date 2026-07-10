"""Unit tests for literature service — offline/stubbed only."""
import pytest
from bgclens.literature.provider import MethodLiteratureSupport, LiteratureRanking
from bgclens.literature.ranker import rank_methods, _topic_to_terms
from bgclens.literature.cache import cache_key


def test_topic_to_terms_basic():
    terms = _topic_to_terms("BGC class enrichment between two clades")
    assert "enrichment" in terms
    assert "clades" in terms or "clade" in terms


def test_topic_to_terms_short():
    terms = _topic_to_terms("BGC")
    assert len(terms) >= 1


def test_cache_key_stable():
    k1 = cache_key(["PCoA"], ["BGC", "genome"], 10)
    k2 = cache_key(["PCoA"], ["genome", "BGC"], 10)
    assert k1 == k2  # sorted terms


def test_offline_fallback():
    ranking = rank_methods(
        method_ids=["pcoa", "permanova"],
        method_display_names={"pcoa": "PCoA", "permanova": "PERMANOVA"},
        topic="BGC diversity",
        provider=None,
    )
    assert ranking.offline is True
    assert len(ranking.method_rankings) == 2
    for s in ranking.method_rankings:
        assert s.support_level == "none"
        assert "offline" in s.note


def test_stubbed_provider():
    """Test that a stub provider is called and results attached."""
    from bgclens.literature.provider import Citation

    class StubProvider:
        def support_for(self, method_terms, topic_terms, window_years=10, max_citations=5):
            return [
                MethodLiteratureSupport(
                    method_id=t,
                    support_level="moderate",
                    work_count=4,
                    citations=[Citation(title="Test paper", authors=["Smith"], year=2023, doi=None, openalex_id=None)],
                )
                for t in method_terms
            ]

    ranking = rank_methods(
        method_ids=["pcoa"],
        method_display_names={"pcoa": "PCoA"},
        topic="ordination BGC diversity",
        provider=StubProvider(),
    )
    assert not ranking.offline
    assert ranking.method_rankings[0].support_level == "moderate"
    assert len(ranking.method_rankings[0].citations) == 1


def test_support_level_ordering():
    """Strong support sorts before weak."""
    from bgclens.literature.ranker import _LEVEL_ORDER
    assert _LEVEL_ORDER["strong"] < _LEVEL_ORDER["weak"]
    assert _LEVEL_ORDER["weak"] < _LEVEL_ORDER["none"]


# ---------------------------------------------------------------------------
# Provider factory tests (all offline — no HTTP calls)
# ---------------------------------------------------------------------------

def test_provider_factory_openalex():
    from bgclens.literature.providers import get_provider
    from bgclens.literature.providers.openalex import OpenAlexProvider
    p = get_provider("openalex")
    assert isinstance(p, OpenAlexProvider)


def test_provider_factory_europepmc():
    from bgclens.literature.providers import get_provider
    from bgclens.literature.providers.europepmc import EuropePMCProvider
    p = get_provider("europepmc")
    assert isinstance(p, EuropePMCProvider)


def test_provider_factory_mibig():
    from bgclens.literature.providers import get_provider
    from bgclens.literature.providers.mibig import MIBiGProvider
    p = get_provider("mibig")
    assert isinstance(p, MIBiGProvider)


def test_provider_factory_unknown_returns_none():
    from bgclens.literature.providers import get_provider
    p = get_provider("unknown_xyz")
    assert p is None


def test_provider_factory_env_var(monkeypatch):
    import os
    from bgclens.literature.providers import get_provider
    from bgclens.literature.providers.europepmc import EuropePMCProvider
    monkeypatch.setenv("BGCLENS_LITERATURE_PROVIDER", "europepmc")
    p = get_provider()
    assert isinstance(p, EuropePMCProvider)


# ---------------------------------------------------------------------------
# New tests for Task 4 fixes
# ---------------------------------------------------------------------------

def test_openalex_abstract_cap_200():
    """_abstract_from_inverted should return at most 200 words."""
    from bgclens.literature.providers.openalex import _abstract_from_inverted

    # Build an inverted index with 250 words
    inverted = {f"word{i}": [i] for i in range(250)}
    result = _abstract_from_inverted(inverted)
    words = result.split()
    assert len(words) <= 200


def test_cooccurrence_query_uses_5_topic_terms():
    """_cooccurrence_query should include up to 5 topic terms, not 3."""
    from bgclens.literature.providers.openalex import _cooccurrence_query

    topic_terms = ["a", "b", "c", "d", "e", "f"]
    query = _cooccurrence_query("PCoA", topic_terms)

    # All of a-e should appear in the query
    for term in ["a", "b", "c", "d", "e"]:
        assert f'"{term}"' in query, f'Expected term "{term}" in query: {query}'

    # f (6th term) should NOT appear
    assert '"f"' not in query, f'Unexpected term "f" found in query: {query}'


def test_merge_supports_takes_max_level():
    """merge_supports should take the better (max) support level."""
    from bgclens.literature.ranker import merge_supports

    moderate_support = [
        MethodLiteratureSupport(
            method_id="pcoa",
            support_level="moderate",
            work_count=3,
            citations=[],
        )
    ]
    strong_support = [
        MethodLiteratureSupport(
            method_id="pcoa",
            support_level="strong",
            work_count=10,
            citations=[],
        )
    ]

    result = merge_supports([moderate_support, strong_support], ["pcoa"])
    assert len(result) == 1
    assert result[0].support_level == "strong"


def test_merge_supports_deduplicates_by_doi():
    """merge_supports should deduplicate citations with the same DOI."""
    from bgclens.literature.provider import Citation
    from bgclens.literature.ranker import merge_supports

    shared_doi = "10.1234/test"
    cite = Citation(title="Shared paper", authors=["Author A"], year=2022, doi=shared_doi, openalex_id=None)

    supports_a = [
        MethodLiteratureSupport(
            method_id="pcoa",
            support_level="moderate",
            work_count=1,
            citations=[cite],
        )
    ]
    supports_b = [
        MethodLiteratureSupport(
            method_id="pcoa",
            support_level="weak",
            work_count=1,
            citations=[cite],
        )
    ]

    result = merge_supports([supports_a, supports_b], ["pcoa"])
    assert len(result) == 1
    assert len(result[0].citations) == 1


def test_offline_fallback_provider_name():
    """_offline_fallback should return LiteratureRanking with provider='offline'."""
    from bgclens.literature.ranker import _offline_fallback

    ranking = _offline_fallback(["pcoa"], "some topic")
    assert ranking.provider == "offline"
