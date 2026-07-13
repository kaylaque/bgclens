"""Smoke tests for render_batch() — multi-block QMD composition."""
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from bgclens.model import BatchReport
from bgclens.report.quarto import render_batch


def _fake_record(cluster_id: str, method_id: str) -> object:
    """Minimal object matching the RunRecord interface render_batch needs."""
    class FakeRecord:
        result_summary = {
            "method": method_id,
            "interpretation": f"Test interpretation for {method_id} on {cluster_id}.",
        }
        run_spec = {"method_id": method_id, "cluster_id": cluster_id, "params": {}}
        inputs_hash = "sha256:abc"
        created_at = "2026-07-13T00:00:00Z"
        literature = {}
    return FakeRecord()


def test_render_batch_writes_qmd(tmp_path):
    records = [
        _fake_record("GCF_001", "alpha_diversity"),
        _fake_record("GCF_002", "alpha_diversity"),
        _fake_record("GCF_001", "fisher_exact"),
    ]
    batch = BatchReport(
        project_name="test_project",
        records=records,
        summary="Cross-cluster summary text.",
        cluster_comparison={"alpha_diversity@GCF_001": "n=10", "alpha_diversity@GCF_002": "n=8"},
    )
    report = render_batch(batch, tmp_path)
    assert report.qmd_path.exists()
    content = report.qmd_path.read_text()
    assert "alpha_diversity" in content
    assert "fisher_exact" in content
    assert "GCF_001" in content
    assert "GCF_002" in content


def test_render_batch_has_summary(tmp_path):
    records = [_fake_record("GCF_001", "alpha_diversity")]
    batch = BatchReport(
        project_name="test",
        records=records,
        summary="This is the cross-cluster narrative.",
    )
    report = render_batch(batch, tmp_path)
    content = report.qmd_path.read_text()
    assert "This is the cross-cluster narrative." in content


def test_render_batch_has_cross_cluster_section(tmp_path):
    records = [
        _fake_record("GCF_001", "alpha_diversity"),
        _fake_record("GCF_002", "alpha_diversity"),
    ]
    batch = BatchReport(
        project_name="test",
        records=records,
        cluster_comparison={"alpha_diversity@GCF_001": "high diversity", "alpha_diversity@GCF_002": "low"},
    )
    report = render_batch(batch, tmp_path)
    content = report.qmd_path.read_text()
    assert "Cross-cluster comparison" in content
    assert "high diversity" in content


def test_render_batch_has_provenance_blocks(tmp_path):
    records = [_fake_record("GCF_001", "alpha_diversity")]
    batch = BatchReport(project_name="test", records=records)
    report = render_batch(batch, tmp_path)
    content = report.qmd_path.read_text()
    assert "Provenance" in content
    assert "method_id" in content


def test_render_batch_never_raises(tmp_path):
    """render_batch must never raise — returns QuartoReport on error."""
    batch = BatchReport(project_name="test", records=[])  # empty records
    report = render_batch(batch, tmp_path)
    assert report is not None
    assert report.qmd_path is not None


def test_render_batch_empty_records(tmp_path):
    batch = BatchReport(project_name="test", records=[], summary="No runs.")
    report = render_batch(batch, tmp_path)
    assert report.qmd_path.exists()
