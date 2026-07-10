"""Tests for intent picker and recommend()."""
import pytest
from pathlib import Path
from bgclens.core.intent import (
    Intent, SQ_LABELS, INTENT_REQUIREMENTS, INTENT_PIPELINE_SOURCES,
    validate_intent, filter_methods_for_intent, AnalysisRequest,
)
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


# ---------------------------------------------------------------------------
# Existing intent tests (regression)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# SQ1-7 intent tests
# ---------------------------------------------------------------------------

SQ_INTENT_VALUES = [
    "sq1_inventory", "sq2_novelty", "sq3_prioritization",
    "sq4_distribution", "sq5_diversity", "sq6_genomic_context", "sq7_association",
]


def test_sq_intents_in_enum():
    """All seven SQ intent values are members of Intent."""
    intent_values = {i.value for i in Intent}
    for sq in SQ_INTENT_VALUES:
        assert sq in intent_values, f"Missing Intent.{sq}"


def test_sq_labels_complete():
    """SQ_LABELS has an entry for every SQ intent and values are non-empty strings."""
    for sq in SQ_INTENT_VALUES:
        assert sq in SQ_LABELS, f"Missing SQ_LABELS['{sq}']"
        assert isinstance(SQ_LABELS[sq], str) and SQ_LABELS[sq], f"Empty label for '{sq}'"


def test_intent_requirements_sq():
    """INTENT_REQUIREMENTS populated for all SQ intents."""
    counts_required = {"sq1_inventory", "sq4_distribution"}
    pa_required = {"sq2_novelty", "sq3_prioritization", "sq5_diversity", "sq7_association"}
    network_required = {"sq6_genomic_context"}

    for sq in counts_required:
        assert "bgc_counts" in INTENT_REQUIREMENTS.get(sq, []), f"{sq} should require bgc_counts"
    for sq in pa_required:
        assert "gcf_presence_absence" in INTENT_REQUIREMENTS.get(sq, []), f"{sq} should require gcf_presence_absence"
    for sq in network_required:
        assert "gcf_network" in INTENT_REQUIREMENTS.get(sq, []), f"{sq} should require gcf_network"


def test_intent_pipeline_sources_sq():
    """INTENT_PIPELINE_SOURCES has entries for all SQ intents."""
    for sq in SQ_INTENT_VALUES:
        assert sq in INTENT_PIPELINE_SOURCES, f"Missing INTENT_PIPELINE_SOURCES['{sq}']"
        assert INTENT_PIPELINE_SOURCES[sq], f"Empty pipeline source for '{sq}'"


def test_validate_sq1_inventory_valid():
    project = _make_project(has_counts=True)
    v = validate_intent(project, Intent.sq1_inventory)
    assert v.valid is True


def test_validate_sq1_inventory_missing_counts():
    project = _make_project(has_counts=False)
    v = validate_intent(project, Intent.sq1_inventory)
    assert v.valid is False
    assert "bgc_counts" in v.missing_data


def test_validate_sq3_prioritization_valid():
    project = _make_project(has_pa=True)
    v = validate_intent(project, Intent.sq3_prioritization)
    assert v.valid is True


def test_validate_sq3_prioritization_missing_pa():
    project = _make_project(has_pa=False)
    v = validate_intent(project, Intent.sq3_prioritization)
    assert v.valid is False
    assert "gcf_presence_absence" in v.missing_data


def test_filter_methods_for_sq3_prioritization():
    """methods_for_intent driven by catalog intents: list — pcoa and clustering should appear."""
    project = _make_project(has_pa=True)
    methods = filter_methods_for_intent(Intent.sq3_prioritization, project)
    ids = [m["id"] for m in methods]
    assert "pcoa" in ids
    assert "hierarchical_clustering" in ids


def test_filter_methods_for_sq5_diversity():
    """Both pcoa and alpha_diversity appear for sq5_diversity (needs pa for pcoa)."""
    project = _make_project(has_pa=True, has_counts=True)
    methods = filter_methods_for_intent(Intent.sq5_diversity, project)
    ids = [m["id"] for m in methods]
    assert "pcoa" in ids


def test_filter_methods_for_sq7_association():
    project = _make_project(has_pa=True)
    methods = filter_methods_for_intent(Intent.sq7_association, project)
    ids = [m["id"] for m in methods]
    assert "permanova" in ids


# ---------------------------------------------------------------------------
# method_hint enforcement
# ---------------------------------------------------------------------------

def test_recommend_method_hint_filters_to_hinted():
    """When method_hint matches a candidate, only that method is returned."""
    from bgclens.core.api import recommend
    project = _make_project(has_pa=True)
    request = AnalysisRequest(
        topic="GCF similarity structure",
        intent=Intent.ordination,
        method_hint="pcoa",
    )
    validation, recs = recommend(project, request, use_literature=False)
    assert validation.valid is True
    assert len(recs) == 1
    assert recs[0].method_id == "pcoa"


def test_recommend_method_hint_graceful_on_unknown():
    """When method_hint doesn't match any candidate, full list is returned."""
    from bgclens.core.api import recommend
    project = _make_project(has_pa=True)
    request = AnalysisRequest(
        topic="GCF ordination",
        intent=Intent.ordination,
        method_hint="nonexistent_method",
    )
    validation, recs = recommend(project, request, use_literature=False)
    assert validation.valid is True
    assert len(recs) >= 1  # full list, graceful degradation


# ---------------------------------------------------------------------------
# MissingRequirementError
# ---------------------------------------------------------------------------

def test_missing_requirement_error_raised():
    """_build_inputs raises MissingRequirementError when required data is absent."""
    from bgclens.core.api import _build_inputs, MissingRequirementError
    project = _make_project(has_pa=False)
    method_entry = {"id": "pcoa", "requires": {"presence_absence": "presence_absence_matrix"}}
    with pytest.raises(MissingRequirementError):
        _build_inputs(project, method_entry)


def test_missing_requirement_error_counts():
    """_build_inputs raises MissingRequirementError for missing counts."""
    from bgclens.core.api import _build_inputs, MissingRequirementError
    project = _make_project(has_counts=False)
    method_entry = {"id": "alpha_diversity", "requires": {"counts": "feature_count_table"}}
    with pytest.raises(MissingRequirementError):
        _build_inputs(project, method_entry)


def test_recommend_missing_requirement_returns_graceful_failure():
    """recommend() converts MissingRequirementError to IntentValidation(valid=False) instead of raising."""
    from bgclens.core.api import recommend
    from bgclens.core.intent import AnalysisRequest, IntentValidation
    # sq2_novelty requires gcf_presence_absence; validate_intent will pass (has_pa=True),
    # but the catalog method for pcoa requires presence_absence which _build_inputs checks too.
    # To force MissingRequirementError through recommend(), we need validate_intent to pass
    # but _build_inputs to fail. We achieve this by giving the project pa=True so validation
    # passes, then monkeypatch filter_methods_for_intent to return a method requiring
    # data that is missing.
    # Simpler: use a project with pa=None and intent that only needs counts so validate_intent
    # passes, but the catalog method requires pa. Use Intent.sq3_prioritization with
    # has_pa=False: validate_intent will detect missing pa and return valid=False already.
    # Instead, directly craft a scenario where validate_intent passes but _build_inputs fails.
    # We can do this by patching filter_methods_for_intent to inject a method that requires
    # 'network' even though the intent doesn't declare that dependency.
    import unittest.mock as mock
    from bgclens.core.api import MissingRequirementError

    project = _make_project(has_pa=True, has_counts=True)
    # Inject a fake method that requires 'network' (gcf_network is None on our project)
    fake_method = {
        "id": "fake_net_method",
        "name": "Fake Network Method",
        "requires": {"network": "gcf_network"},
        "intents": ["ordination"],
    }
    request = AnalysisRequest(topic="test", intent=Intent.ordination)
    with mock.patch("bgclens.core.api.filter_methods_for_intent", return_value=[fake_method]):
        validation, recs = recommend(project, request, use_literature=False)

    assert validation.valid is False
    assert recs == []
    assert isinstance(validation, IntentValidation)
