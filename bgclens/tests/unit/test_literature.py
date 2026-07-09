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
