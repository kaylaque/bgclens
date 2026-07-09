"""Tests for BGCFlow project detection."""
import pytest
from pathlib import Path
import tempfile, os
from bgclens.adapters.detect import detect_project


def _make_project(tmp_path: Path, files: list[str]) -> Path:
    for f in files:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("dummy")
    return tmp_path


def test_detect_invalid_path():
    with pytest.raises(ValueError, match="does not exist"):
        detect_project(Path("/nonexistent/path/xyz"))


def test_detect_no_pipeline_output(tmp_path):
    with pytest.raises(ValueError, match="No BGCFlow pipeline output"):
        detect_project(tmp_path)


def test_detect_antismash(tmp_path):
    _make_project(tmp_path, ["tables/df_antismash_7.0.1_summary.csv"])
    manifest = detect_project(tmp_path)
    assert "antismash" in manifest.available_pipelines


def test_detect_bigscape(tmp_path):
    _make_project(tmp_path, ["tables/df_bigscape_cluster_summary.csv"])
    manifest = detect_project(tmp_path)
    assert "bigscape" in manifest.available_pipelines


def test_detect_duckdb(tmp_path):
    _make_project(tmp_path, [
        "tables/df_gtdb_meta.csv",
        "dbt_bgcflow.duckdb",
    ])
    manifest = detect_project(tmp_path)
    assert manifest.duckdb_path is not None
    assert manifest.duckdb_path.name == "dbt_bgcflow.duckdb"
