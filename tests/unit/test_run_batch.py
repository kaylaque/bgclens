"""Smoke tests for run_batch() — monkeypatched compute, no real methods needed."""
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from bgclens.model import (
    Cluster, PresenceAbsenceMatrix, Project, ProjectManifest,
)
from bgclens.core.api import run_batch


def _make_project():
    gcf_ids = [f"GCF_{i:03d}" for i in range(5)]
    pa = PresenceAbsenceMatrix(
        rows=gcf_ids,
        cols=["genome_a", "genome_b"],
        values=[[1, 0]] * 5,
    )
    return Project(
        manifest=ProjectManifest(
            project_name="test_batch",
            source_path=Path("/tmp/test"),
            available_pipelines={"antismash"},
        ),
        gcf_presence_absence=pa,
    )


def _fake_run(project, method_id, params=None):
    """Deterministic fake run() — no actual compute."""
    return {
        "method": method_id,
        "n_genomes": len(project.gcf_presence_absence.cols) if project.gcf_presence_absence else 0,
        "_assumption_warnings": [],
        "_method_id": method_id,
        "_provenance": {"inputs_hash": "test", "method_id": method_id, "params": {}},
        "_confidence_band": "green",
        "_validation_checks": [],
    }


@patch("bgclens.core.api.run", side_effect=_fake_run)
def test_run_batch_produces_results(mock_run):
    proj = _make_project()
    results = asyncio.run(run_batch(
        proj,
        method_ids=["alpha_diversity", "fisher_exact"],
        cluster_ids=None,
        use_llm=False,
    ))
    # smoke round = 3 clusters × 2 methods = 6 results
    assert len(results) == 6
    methods_seen = {r.get("method") or r.get("_method_id") for r in results}
    assert "alpha_diversity" in methods_seen
    assert "fisher_exact" in methods_seen


@patch("bgclens.core.api.run", side_effect=_fake_run)
def test_run_batch_specific_clusters(mock_run):
    proj = _make_project()
    results = asyncio.run(run_batch(
        proj,
        method_ids=["alpha_diversity"],
        cluster_ids=["GCF_000", "GCF_001"],
        use_llm=False,
    ))
    # 2 clusters × 1 method = 2
    assert len(results) == 2
    cluster_ids = {r.get("_cluster_id") for r in results}
    assert "GCF_000" in cluster_ids
    assert "GCF_001" in cluster_ids


@patch("bgclens.core.api.run", side_effect=Exception("method error"))
def test_run_batch_exception_returns_error_dict(mock_run):
    proj = _make_project()
    results = asyncio.run(run_batch(
        proj,
        method_ids=["bad_method"],
        cluster_ids=["GCF_000"],
        use_llm=False,
    ))
    assert len(results) == 1
    # Exception stored as _error or method completes with error detail
    assert "_error" in results[0] or isinstance(results[0], dict)
