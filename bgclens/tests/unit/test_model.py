"""Smoke tests for canonical model instantiation."""
from bgclens.model import (
    FeatureCountTable,
    MetadataTable,
    PresenceAbsenceMatrix,
    ProjectManifest,
    QualityTable,
    TaxonomyTable,
)
from pathlib import Path
import numpy as np


def test_presence_absence_matrix_roundtrip():
    pa = PresenceAbsenceMatrix(
        rows=["GCF_1", "GCF_2"],
        cols=["genome_a", "genome_b", "genome_c"],
        values=[[1, 0, 1], [0, 1, 1]],
    )
    arr = pa.to_numpy()
    assert arr.shape == (2, 3)
    assert arr[0, 0] == 1
    assert arr[1, 0] == 0


def test_feature_count_table_roundtrip():
    fct = FeatureCountTable(
        genome_ids=["g1", "g2"],
        features=["terpene", "nrps"],
        counts=[[3, 1], [0, 2]],
    )
    arr = fct.to_numpy()
    assert arr.shape == (2, 2)
    assert arr[0, 0] == 3


def test_project_manifest_empty_pipelines():
    m = ProjectManifest(
        project_name="test",
        source_path=Path("/tmp/test"),
        available_pipelines=set(),
    )
    assert m.project_name == "test"
    assert len(m.available_pipelines) == 0
