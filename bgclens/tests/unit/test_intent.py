"""Tests for intent picker and recommend()."""
import pytest
from pathlib import Path
from bgclens.core.intent import Intent, validate_intent, filter_methods_for_intent, AnalysisRequest
from bgclens.model import (
    Project, ProjectManifest, PresenceAbsenceMatrix, FeatureCountTable,
    TaxonomyTable, MetadataTable
)


def _make_project(has_pa: bool = True, has_counts: bool = True) -> Project:
    manifest = ProjectManifest(
        project_name="test",
        source_path=Path("/tmp/test"),
        available_pipelines={"antismash", "bigscape"},
    )
    pa = None
    if has_pa:
        pa = PresenceAbsenceMatrix(
            rows=["GCF_1", "GCF_2"],
            cols=["g1", "g2", "g3", "g4", "g5"],
            values=[[1, 0, 1, 0, 1], [0, 1, 1, 1, 0]],
        )
    counts = None
    if has_counts:
        counts = FeatureCountTable(
            genome_ids=["g1", "g2", "g3", "g4", "g5"],
            features=["terpene", "nrps"],
            counts=[[1, 0], [0, 2], [1, 1], [2, 0], [0, 1]],
        )
    return Project(manifest=manifest, gcf_presence_absence=pa, bgc_counts=counts)


def test_validate_ordination_valid():
    project = _make_project(has_pa=True)
    v = validate_intent(project, Intent.ordination)
    assert v.valid is True


def test_validate_ordination_missing_pa():
    project = _make_project(has_pa=False)
    v = validate_intent(project, Intent.ordination)
    assert v.valid is False
    assert "gcf_presence_absence" in v.missing_data
    assert "bigscape" in v.suggestion.lower()


def test_validate_enrichment_valid():
    project = _make_project(has_counts=True)
    v = validate_intent(project, Intent.enrichment)
    assert v.valid is True


def test_validate_enrichment_missing_counts():
    project = _make_project(has_counts=False)
    v = validate_intent(project, Intent.enrichment)
    assert v.valid is False
    assert "antismash" in v.suggestion.lower()


def test_filter_methods_for_ordination():
    project = _make_project(has_pa=True)
    methods = filter_methods_for_intent(Intent.ordination, project)
    ids = [m["id"] for m in methods]
    assert "pcoa" in ids


def test_filter_methods_for_enrichment():
    project = _make_project(has_counts=True)
    methods = filter_methods_for_intent(Intent.enrichment, project)
    ids = [m["id"] for m in methods]
    assert "fisher_enrichment" in ids


def test_recommend_ordination_no_literature():
    """recommend() with use_literature=False — fast, no network calls."""
    from bgclens.core.api import recommend
    project = _make_project(has_pa=True)
    request = AnalysisRequest(topic="BGC diversity across clades", intent=Intent.ordination)
    validation, recs = recommend(project, request, use_literature=False)
    assert validation.valid is True
    assert len(recs) >= 1
    # At least one method marked as recommended
    assert any(r.is_recommended for r in recs)
    # All have cost info
    for r in recs:
        assert r.cost_class in ("Safe", "Heavy", "Likely-to-fail")


def test_recommend_invalid_intent():
    project = _make_project(has_pa=False, has_counts=False)
    from bgclens.core.api import recommend
    request = AnalysisRequest(topic="any", intent=Intent.ordination)
    validation, recs = recommend(project, request, use_literature=False)
    assert validation.valid is False
    assert recs == []
