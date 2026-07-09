"""Tests for BGCFlow project detection."""
import pytest
from pathlib import Path
import tempfile, os
from bgclens.adapters.detect import detect_project
from bgclens.adapters.csv_adapter import find_antismash_summary


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


@pytest.mark.parametrize("version", ["6.1.1", "7.0.1", "7.1.0", "8.0.4"])
def test_detect_antismash_any_version(tmp_path, version):
    _make_project(tmp_path, [f"tables/df_antismash_{version}_summary.csv"])
    manifest = detect_project(tmp_path)
    assert "antismash" in manifest.available_pipelines


def test_find_antismash_summary_prefers_newest_version(tmp_path):
    _make_project(tmp_path, [
        "tables/df_antismash_7.1.0_summary.csv",
        "tables/df_antismash_8.0.4_summary.csv",
        "tables/df_antismash_6.1.1_summary.csv",
    ])
    assert find_antismash_summary(tmp_path).name == "df_antismash_8.0.4_summary.csv"


def test_find_antismash_summary_absent(tmp_path):
    assert find_antismash_summary(tmp_path) is None


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
