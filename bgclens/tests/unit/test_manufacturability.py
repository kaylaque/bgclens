"""Unit tests for manufacturability Tier-A features — all offline."""
import pytest
from unittest.mock import MagicMock
from bgclens.manufacturability import compute_features, compute_profile, reorder_for_manufacturability
from bgclens.manufacturability.features import TierAFeatures
from bgclens.manufacturability.profile import ManufacturabilityProfile


def _mock_project(bgc_counts_data=None, quality_data=None):
    """Build a minimal mock Project."""
    import pandas as pd
    project = MagicMock()
    if bgc_counts_data is not None:
        project.bgc_counts = MagicMock()
        project.bgc_counts.data = pd.DataFrame(bgc_counts_data)
    else:
        project.bgc_counts = None
    if quality_data is not None:
        project.quality = MagicMock()
        project.quality.data = pd.DataFrame(quality_data)
    else:
        project.quality = None
    return project


def test_compute_features_empty_project():
    project = _mock_project()
    features = compute_features(project)
    assert isinstance(features, TierAFeatures)
    assert features.n_bgcs == 0
    assert features.tractability_score == 0.0


def test_compute_features_bgc_counts():
    project = _mock_project(bgc_counts_data={"RiPP": [5, 3], "PKS-I": [1, 2]})
    features = compute_features(project)
    assert features.n_bgcs == 11  # 5+3+1+2
    assert features.bgc_class_counts["RiPP"] == 8
    assert features.bgc_class_counts["PKS-I"] == 3


def test_tractability_score_ripp_heavy():
    """High-RiPP collection should have high tractability."""
    project = _mock_project(bgc_counts_data={"RiPP": [10, 10]})
    features = compute_features(project)
    assert features.tractability_score >= 0.85  # RiPP tractability is 0.9


def test_tractability_score_pksi_heavy():
    """High-PKS-I collection should have low tractability."""
    project = _mock_project(bgc_counts_data={"PKS-I": [10, 10]})
    features = compute_features(project)
    assert features.tractability_score <= 0.5


def test_compute_features_never_raises():
    """compute_features never raises even with broken project data."""
    broken = MagicMock()
    broken.bgc_counts.data = None  # will cause an error internally
    broken.quality.data = None
    features = compute_features(broken)
    assert isinstance(features, TierAFeatures)
    assert len(features.notes) > 0  # error logged to notes


def test_reorder_high_tractability():
    """High tractability (>=0.7) boosts enrichment and diversity to front."""
    recs = [MagicMock(method_id="pcoa"), MagicMock(method_id="fisher_enrichment"), MagicMock(method_id="diversity")]
    profile = ManufacturabilityProfile(tractability_score=0.85, n_bgcs=10, top_class="RiPP", notes=[])
    reordered = reorder_for_manufacturability(recs, profile)
    ids = [r.method_id for r in reordered]
    assert ids[0] in ("fisher_enrichment", "diversity")


def test_reorder_low_tractability():
    """Low tractability (<0.5) boosts ordination to front."""
    recs = [MagicMock(method_id="fisher_enrichment"), MagicMock(method_id="pcoa"), MagicMock(method_id="clustering")]
    profile = ManufacturabilityProfile(tractability_score=0.3, n_bgcs=10, top_class="PKS-I", notes=[])
    reordered = reorder_for_manufacturability(recs, profile)
    ids = [r.method_id for r in reordered]
    assert ids[0] in ("pcoa", "clustering")


def test_reorder_neutral_unchanged():
    """Middle tractability: order unchanged."""
    recs = [MagicMock(method_id="pcoa"), MagicMock(method_id="fisher_enrichment")]
    profile = ManufacturabilityProfile(tractability_score=0.6, n_bgcs=5, top_class="NRP", notes=[])
    reordered = reorder_for_manufacturability(recs, profile)
    assert [r.method_id for r in reordered] == ["pcoa", "fisher_enrichment"]
