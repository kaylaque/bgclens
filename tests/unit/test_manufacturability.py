"""Unit tests for manufacturability Tier-A features — all offline."""
from unittest.mock import MagicMock

from bgclens.manufacturability import (
    compute_features,
    compute_profile,
    reorder_for_manufacturability,
)
from bgclens.manufacturability.features import TierAFeatures
from bgclens.manufacturability.profile import ManufacturabilityProfile
from bgclens.model import (
    FeatureCountTable,
    Project,
    ProjectManifest,
)


def _project(features: list[str], counts: list[list[int]]) -> Project:
    """Build a real Project carrying a populated FeatureCountTable."""
    genome_ids = [f"GCA_{i:09d}.1" for i in range(len(counts))]
    manifest = ProjectManifest(project_name="test", source_path="/tmp/test")
    return Project(
        manifest=manifest,
        bgc_counts=FeatureCountTable(
            genome_ids=genome_ids,
            features=features,
            counts=counts,
        ),
    )


def test_compute_features_empty_project():
    """No bgc_counts table → zero score, never raises, honest note recorded."""
    project = Project(manifest=ProjectManifest(project_name="empty", source_path="/tmp/x"))
    features = compute_features(project)
    assert isinstance(features, TierAFeatures)
    assert features.n_bgcs == 0
    assert features.tractability_score == 0.0
    assert features.gc_content_mean is None
    assert len(features.notes) > 0  # honest notes always populated


def test_compute_features_never_raises_on_broken_project():
    """A malformed project must not raise — errors are logged to notes."""
    broken = MagicMock()
    broken.bgc_counts.features = ["RiPP"]
    broken.bgc_counts.counts = [[1]]
    broken.bgc_counts.to_numpy.side_effect = ValueError("boom")
    features = compute_features(broken)
    assert isinstance(features, TierAFeatures)
    assert any("failed" in n for n in features.notes)


def test_compute_features_real_table_class_totals():
    """Per-class totals sum counts over genomes for each feature column."""
    project = _project(
        features=["RiPP-like", "T1PKS"],
        counts=[[5, 1], [3, 2]],
    )
    features = compute_features(project)
    assert features.n_bgcs == 11  # 5+3+1+2
    assert features.bgc_class_counts["RiPP-like"] == 8
    assert features.bgc_class_counts["T1PKS"] == 3
    assert features.gc_content_mean is None


def test_tractability_and_top_class_ripp_terpene_heavy():
    """RiPP/terpene-dominated set → high tractability and a real top_class."""
    # Mirrors the live Lactobacillus_delbrueckii label shapes.
    project = _project(
        features=[
            "lanthipeptide-class-iii",
            "RiPP-like",
            "terpene-precursor",
            "lanthipeptide-class-iv",
        ],
        counts=[[1, 1, 1, 1], [0, 0, 1, 0], [0, 1, 1, 1], [1, 1, 1, 0]],
    )
    features = compute_features(project)
    profile = compute_profile(features)

    assert profile.tractability_score > 0.8  # all RiPP/terpene → high
    assert profile.top_class == "terpene-precursor"  # 4 counts, the max
    # terpene → yeast chassis from the fixed panel
    assert profile.chassis_hint is not None
    assert profile.chassis_hint["organism"] == "S. cerevisiae"
    # no NRPS/PKS present → only the standing GC blocker
    assert any("GC not derivable" in b for b in profile.blockers)
    assert not any("PPTase" in b for b in profile.blockers)


def test_pksi_heavy_low_tractability_and_blockers():
    """PKS-I heavy set → low tractability, PPTase + megasynthase blockers, S. albus hint."""
    project = _project(features=["T1PKS", "NRPS"], counts=[[10, 2], [10, 3]])
    features = compute_features(project)
    profile = compute_profile(features)

    assert profile.tractability_score < 0.5
    assert profile.top_class == "T1PKS"
    assert profile.chassis_hint["organism"] == "S. albus J1074"
    assert any("PPTase" in b for b in profile.blockers)
    assert any("megasynthase" in b for b in profile.blockers)


def test_chassis_hint_none_when_no_top_class():
    features = TierAFeatures()
    profile = compute_profile(features)
    assert profile.top_class is None
    assert profile.chassis_hint is None


def test_reorder_high_tractability():
    """High tractability (>=0.7) boosts enrichment + diversity to front."""
    recs = [
        MagicMock(method_id="pcoa"),
        MagicMock(method_id="fisher_enrichment"),
        MagicMock(method_id="alpha_diversity"),
    ]
    profile = ManufacturabilityProfile(
        tractability_score=0.85, n_bgcs=10, top_class="RiPP-like"
    )
    reordered = reorder_for_manufacturability(recs, profile)
    ids = [r.method_id for r in reordered]
    assert ids[0] in ("fisher_enrichment", "alpha_diversity")


def test_reorder_low_tractability():
    """Low tractability (<0.5) boosts ordination + clustering to front."""
    recs = [
        MagicMock(method_id="fisher_enrichment"),
        MagicMock(method_id="pcoa"),
        MagicMock(method_id="hierarchical_clustering"),
    ]
    profile = ManufacturabilityProfile(
        tractability_score=0.3, n_bgcs=10, top_class="T1PKS"
    )
    reordered = reorder_for_manufacturability(recs, profile)
    ids = [r.method_id for r in reordered]
    assert ids[0] in ("pcoa", "pca", "hierarchical_clustering")


def test_reorder_neutral_unchanged():
    """Middle tractability: order unchanged."""
    recs = [MagicMock(method_id="pcoa"), MagicMock(method_id="fisher_enrichment")]
    profile = ManufacturabilityProfile(
        tractability_score=0.6, n_bgcs=5, top_class="NRPS"
    )
    reordered = reorder_for_manufacturability(recs, profile)
    assert [r.method_id for r in reordered] == ["pcoa", "fisher_enrichment"]
