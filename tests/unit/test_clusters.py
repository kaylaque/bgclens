"""Smoke tests for bgclens.core.clusters — deterministic, no LLM."""
from pathlib import Path
import pytest

from bgclens.model import (
    Cluster, PresenceAbsenceMatrix, Project, ProjectManifest,
    TaxonomyTable, NetworkEdgeList,
)
from bgclens.core.clusters import list_clusters, select_smoke_clusters, _novelty_band


def _make_project(gcf_ids=None, genome_ids=None, with_taxonomy=False, with_network=False):
    gcf_ids = gcf_ids or ["GCF_001", "GCF_002", "GCF_003"]
    genome_ids = genome_ids or ["genome_a", "genome_b"]
    values = [[1, 0]] * len(gcf_ids)

    pa = PresenceAbsenceMatrix(rows=gcf_ids, cols=genome_ids, values=values)

    taxonomy = None
    if with_taxonomy:
        taxonomy = TaxonomyTable(
            genome_ids=genome_ids,
            genus=["Streptomyces", "Aspergillus"],
            species=["coelicolor", "niger"],
        )

    network = None
    if with_network:
        network = NetworkEdgeList(
            nodes=gcf_ids,
            edges=[(gcf_ids[0], gcf_ids[1], 0.9), (gcf_ids[0], gcf_ids[2], 0.5)],
        )

    return Project(
        manifest=ProjectManifest(
            project_name="test",
            source_path=Path("/tmp/test_project"),
            available_pipelines={"antismash", "bigscape"},
        ),
        gcf_presence_absence=pa,
        taxonomy=taxonomy,
        gcf_network=network,
    )


def test_list_clusters_basic():
    proj = _make_project()
    clusters = list_clusters(proj)
    assert len(clusters) == 3
    for c in clusters:
        assert isinstance(c, Cluster)
        assert c.cluster_id in ["GCF_001", "GCF_002", "GCF_003"]
        assert c.novelty_band in ("high", "medium", "low", "novel-candidate")


def test_list_clusters_empty_project():
    proj = _make_project()
    proj.gcf_presence_absence = None
    clusters = list_clusters(proj)
    assert clusters == []


def test_list_clusters_with_taxonomy():
    proj = _make_project(with_taxonomy=True)
    clusters = list_clusters(proj)
    assert len(clusters) == 3
    # At least one cluster should have an organism set (Streptomyces coelicolor is present in genome_a)
    organisms = [c.organism for c in clusters if c.organism]
    assert len(organisms) > 0


def test_list_clusters_nrps_type_inference():
    proj = _make_project(gcf_ids=["nrps_GCF_001", "terpene_GCF_002", "pks_GCF_003"])
    clusters = list_clusters(proj)
    type_map = {c.cluster_id: c.cluster_type for c in clusters}
    assert type_map["nrps_GCF_001"] == "NRPS"
    assert type_map["terpene_GCF_002"] == "terpene"
    assert type_map["pks_GCF_003"] == "PKS"


def test_novelty_band_thresholds():
    assert _novelty_band(None) == "low"
    assert _novelty_band(0.1) == "low"
    assert _novelty_band(0.29) == "low"
    assert _novelty_band(0.3) == "medium"   # boundary: < 0.3 is low, >= 0.3 is medium
    assert _novelty_band(0.5) == "medium"
    assert _novelty_band(0.6) == "high"     # boundary: < 0.6 is medium, >= 0.6 is high
    assert _novelty_band(0.9) == "novel-candidate"


def test_select_smoke_clusters_default():
    proj = _make_project(gcf_ids=[f"GCF_{i:03d}" for i in range(10)])
    clusters = list_clusters(proj)
    smoke = select_smoke_clusters(clusters, n=3)
    assert len(smoke) == 3


def test_select_smoke_clusters_fewer_than_n():
    proj = _make_project(gcf_ids=["GCF_001", "GCF_002"])
    clusters = list_clusters(proj)
    smoke = select_smoke_clusters(clusters, n=5)
    assert len(smoke) == 2  # capped at actual count


def test_select_smoke_clusters_empty():
    assert select_smoke_clusters([], n=3) == []


def test_select_smoke_clusters_diverse_types():
    # Force distinct types so the diversity selection has something to pick
    gcf_ids = ["nrps_GCF_001", "terpene_GCF_002", "pks_GCF_003", "nrps_GCF_004"]
    proj = _make_project(gcf_ids=gcf_ids)
    clusters = list_clusters(proj)
    smoke = select_smoke_clusters(clusters, n=3)
    types = {c.cluster_type for c in smoke}
    assert len(types) >= 2  # should pick diverse types
