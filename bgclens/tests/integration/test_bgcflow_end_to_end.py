"""
End-to-end test: BGCFlow → BGCLens.

Two entry paths:

1. **Full pipeline (slow, Linux only)**
   Runs BGCFlow on the bundled mq_saccharopolyspora example, waits for it to
   finish, then drives BGCLens on the resulting processed directory.
   Skipped unless:
     - `pytest -m bgcflow` is passed, OR `BGCLENS_RUN_BGCFLOW=1` is set
     - `snakemake` is on PATH
     - System is Linux (Singularity required by BGCFlow containers)
     - `BGCFLOW_DIR` points to the cloned BGCFlow repository

2. **Pre-computed path (fast, any OS)**
   If `BGCFLOW_PROCESSED_DIR` env var points to an existing BGCFlow processed
   directory (e.g. from a prior run or a downloaded demo), skips BGCFlow and
   goes straight to BGCLens. This is how you test on Mac once you have real data.

Usage examples
--------------
# Point at pre-computed data (fast path):
BGCFLOW_PROCESSED_DIR=/path/to/mq_saccharopolyspora pytest tests/integration/test_bgcflow_end_to_end.py -v

# Full pipeline (Linux CI):
BGCFLOW_DIR=/path/to/bgcflow BGCLENS_RUN_BGCFLOW=1 pytest tests/integration/test_bgcflow_end_to_end.py -v -m bgcflow
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
import yaml

# ── Environment gates ────────────────────────────────────────────────────────

BGCFLOW_DIR = Path(os.environ.get("BGCFLOW_DIR", "")) if os.environ.get("BGCFLOW_DIR") else None
BGCFLOW_PROCESSED_DIR = Path(os.environ.get("BGCFLOW_PROCESSED_DIR", "")) if os.environ.get("BGCFLOW_PROCESSED_DIR") else None
RUN_BGCFLOW = os.environ.get("BGCLENS_RUN_BGCFLOW", "0") == "1"

_has_snakemake = shutil.which("snakemake") is not None
_is_linux = platform.system() == "Linux"
_bgcflow_repo_exists = BGCFLOW_DIR is not None and BGCFLOW_DIR.is_dir()
_precomputed_exists = BGCFLOW_PROCESSED_DIR is not None and BGCFLOW_PROCESSED_DIR.is_dir()

# Default: look for bgcflow repo sibling to bgclens
_DEFAULT_BGCFLOW = Path(__file__).parent.parent.parent.parent / "bgcflow"
if not _bgcflow_repo_exists and _DEFAULT_BGCFLOW.is_dir():
    BGCFLOW_DIR = _DEFAULT_BGCFLOW
    _bgcflow_repo_exists = True

_EXAMPLE_NAME = "mq_saccharopolyspora"
_EXAMPLE_SRC = BGCFLOW_DIR / ".examples" / _EXAMPLE_NAME if _bgcflow_repo_exists else None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _setup_bgcflow_project(work_dir: Path) -> Path:
    """Copy the mq_saccharopolyspora example into a fresh work directory."""
    assert _EXAMPLE_SRC is not None and _EXAMPLE_SRC.exists(), \
        f"Example not found at {_EXAMPLE_SRC}"

    project_dir = work_dir / _EXAMPLE_NAME
    project_dir.mkdir(parents=True)

    # BGCFlow expects: <project>/config/project_config.yaml + samples.csv
    config_dir = project_dir / "config"
    config_dir.mkdir()

    for f in _EXAMPLE_SRC.iterdir():
        shutil.copy(f, config_dir / f.name)

    # BGCFlow also needs a top-level config pointing at the project
    bgcflow_config = {
        "projects": [
            {
                "name": _EXAMPLE_NAME,
                "pep": str(config_dir / "project_config.yaml"),
            }
        ]
    }
    (project_dir / "bgcflow_config.yaml").write_text(yaml.dump(bgcflow_config))
    return project_dir


def _run_bgcflow(bgcflow_repo: Path, work_dir: Path, *, cores: int = 4, dry_run: bool = False) -> Path:
    """Run BGCFlow snakemake on the prepared work_dir. Returns processed output path."""
    snakefile = bgcflow_repo / "workflow" / "Snakefile"
    assert snakefile.exists(), f"Snakefile not found at {snakefile}"

    cmd = [
        "snakemake",
        "--snakefile", str(snakefile),
        "--directory", str(work_dir),
        "--cores", str(cores),
        "--use-conda",
        "--rerun-incomplete",
        "--nolock",
    ]
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, capture_output=False, text=True, cwd=work_dir)
    if result.returncode != 0:
        raise RuntimeError(f"BGCFlow failed (exit {result.returncode}). Check snakemake output above.")

    processed = work_dir / "data" / "processed" / _EXAMPLE_NAME
    if not dry_run:
        assert processed.exists(), f"BGCFlow finished but processed dir not found: {processed}"
    return processed


def _assert_bgclens_processes(processed_dir: Path) -> None:
    """Run the full BGCLens engine on a processed dir and assert non-empty output."""
    from bgclens.core.api import open_project, run
    from bgclens.viz import render
    from bgclens.interpret import interpret

    proj = open_project(processed_dir)
    manifest = proj.manifest

    assert len(manifest.available_pipelines) >= 1, \
        f"No BGCFlow pipelines detected in {processed_dir}. " \
        f"Expected at least antismash or bigscape."

    # Choose the most broadly available method
    if proj.gcf_presence_absence is not None:
        method_id = "pcoa"
        assert len(proj.gcf_presence_absence.cols) >= 2, \
            "Need at least 2 genomes for PCoA"
    elif proj.bgc_counts is not None:
        method_id = "alpha_diversity"
    else:
        pytest.skip("No GCF presence/absence or BGC count data found — cannot run analysis.")

    result = run(proj, method_id, {})
    assert result.get("method") == method_id

    svg_bytes, png_bytes = render(result, proj.metadata)
    assert len(svg_bytes) > 100, "SVG output is empty"
    assert png_bytes[:4] == b"\x89PNG", "PNG header invalid"

    interp = interpret(result, assumption_warnings=result.get("_assumption_warnings", []), use_llm=False)
    assert "## Method" in interp["final_text"]
    assert "## Result" in interp["final_text"]
    assert len(interp["final_text"]) > 200


# ── Test class: pre-computed path (any OS, fast) ─────────────────────────────

@pytest.mark.skipif(not _precomputed_exists, reason=(
    "Set BGCFLOW_PROCESSED_DIR=/path/to/bgcflow/processed/mq_saccharopolyspora "
    "to run BGCLens on pre-computed BGCFlow output."
))
class TestBGCLensOnPrecomputedOutput:
    """Fast path: validate BGCLens on an existing BGCFlow processed directory."""

    def test_detect_project(self):
        """BGCLens detects pipelines in the pre-computed output."""
        from bgclens.core.api import open_project
        proj = open_project(BGCFLOW_PROCESSED_DIR)
        assert len(proj.manifest.available_pipelines) >= 1
        print(f"\nDetected pipelines: {sorted(proj.manifest.available_pipelines)}")

    def test_load_canonical_types(self):
        """Canonical data types populate from real BGCFlow output."""
        from bgclens.core.api import open_project
        proj = open_project(BGCFLOW_PROCESSED_DIR)
        # At least one of the canonical tables must load
        has_data = any([
            proj.gcf_presence_absence is not None,
            proj.bgc_counts is not None,
            proj.taxonomy is not None,
            proj.quality is not None,
        ])
        assert has_data, "No canonical data loaded from BGCFlow output"

    def test_full_bgclens_pipeline(self):
        """Full BGCLens engine: ingest → run → viz → interpret."""
        _assert_bgclens_processes(BGCFLOW_PROCESSED_DIR)

    def test_recommend_returns_valid_methods(self):
        """Recommend returns at least one valid method for the real dataset."""
        from bgclens.core.api import open_project, recommend
        from bgclens.core.intent import AnalysisRequest, Intent
        proj = open_project(BGCFLOW_PROCESSED_DIR)
        request = AnalysisRequest(
            topic="BGC diversity in Saccharopolyspora genomes",
            intent=Intent.ordination,
        )
        validation, recs = recommend(proj, request, use_literature=False)
        assert validation.valid is True
        assert len(recs) >= 1
        assert any(r.is_recommended for r in recs)

    def test_web_api_on_real_data(self):
        """Web API endpoints work on real BGCFlow data."""
        from bgclens_web.api.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)

        r = client.post("/api/open", json={"path": str(BGCFLOW_PROCESSED_DIR)})
        assert r.status_code == 200
        data = r.json()
        assert data["genome_count"] >= 2

        r2 = client.post("/api/recommend", json={
            "path": str(BGCFLOW_PROCESSED_DIR),
            "intent": "ordination",
            "topic": "Saccharopolyspora BGC diversity",
            "use_literature": False,
        })
        assert r2.status_code == 200
        assert r2.json()["valid"] is True

        r3 = client.post("/api/run", json={
            "path": str(BGCFLOW_PROCESSED_DIR),
            "method_id": "pcoa",
            "params": {},
            "use_llm": False,
        })
        assert r3.status_code == 200
        d = r3.json()
        assert len(d["figure_svg_b64"]) > 100
        assert "## Method" in d["interpretation"]


# ── Test class: full BGCFlow run (Linux + Singularity, slow) ─────────────────

_full_pipeline_reason = (
    "Full BGCFlow pipeline test requires: "
    "(1) Linux OS, "
    "(2) snakemake on PATH, "
    "(3) BGCFlow repo (set BGCFLOW_DIR or place bgcflow/ next to bgclens/), "
    "(4) BGCLENS_RUN_BGCFLOW=1 env var. "
    f"Current: OS={platform.system()}, snakemake={'yes' if _has_snakemake else 'no'}, "
    f"bgcflow_repo={'yes' if _bgcflow_repo_exists else 'no'}, "
    f"RUN_BGCFLOW={RUN_BGCFLOW}."
)

@pytest.mark.bgcflow
@pytest.mark.slow
@pytest.mark.skipif(
    not (RUN_BGCFLOW and _has_snakemake and _is_linux and _bgcflow_repo_exists),
    reason=_full_pipeline_reason,
)
class TestBGCFlowThenBGCLens:
    """Full pipeline: BGCFlow run → BGCLens processing."""

    @pytest.fixture(scope="class")
    def bgcflow_work_dir(self, tmp_path_factory):
        """Set up a BGCFlow work directory with the mq_saccharopolyspora example."""
        work_dir = tmp_path_factory.mktemp("bgcflow_run")
        _setup_bgcflow_project(work_dir)
        return work_dir

    @pytest.fixture(scope="class")
    def processed_dir(self, bgcflow_work_dir):
        """Run BGCFlow and return the processed output directory."""
        print(f"\nRunning BGCFlow on {_EXAMPLE_NAME} (this may take 30–120 minutes)…")
        print(f"Work dir: {bgcflow_work_dir}")
        start = time.time()
        p = _run_bgcflow(BGCFLOW_DIR, bgcflow_work_dir, cores=4)
        elapsed = time.time() - start
        print(f"BGCFlow completed in {elapsed/60:.1f} minutes. Output: {p}")
        return p

    def test_dry_run_succeeds(self, bgcflow_work_dir):
        """BGCFlow dry-run resolves all rules without error."""
        _run_bgcflow(BGCFLOW_DIR, bgcflow_work_dir, cores=1, dry_run=True)

    def test_processed_dir_has_expected_tables(self, processed_dir):
        """BGCFlow produced the expected output tables."""
        expected = [
            "tables/df_antismash_7.0.1_summary.csv",
            "tables/df_bigscape_cluster_summary.csv",
        ]
        for rel in expected:
            assert (processed_dir / rel).exists(), \
                f"Expected BGCFlow output missing: {processed_dir / rel}"

    def test_bgclens_detects_pipelines(self, processed_dir):
        """BGCLens detects BGCFlow pipelines in the processed output."""
        from bgclens.core.api import open_project
        proj = open_project(processed_dir)
        assert "antismash" in proj.manifest.available_pipelines
        assert "bigscape" in proj.manifest.available_pipelines

    def test_bgclens_full_pipeline_on_bgcflow_output(self, processed_dir):
        """Full BGCLens engine runs successfully on real BGCFlow output."""
        _assert_bgclens_processes(processed_dir)

    def test_genome_count_matches_samples(self, processed_dir):
        """Number of genomes in BGCLens matches BGCFlow samples.csv."""
        from bgclens.core.api import open_project
        import csv
        proj = open_project(processed_dir)

        # Count samples from original config
        samples_csv = BGCFLOW_DIR / ".examples" / _EXAMPLE_NAME / "samples.csv"
        with open(samples_csv) as f:
            expected_count = sum(1 for _ in csv.DictReader(f))

        if proj.gcf_presence_absence is not None:
            actual_count = len(proj.gcf_presence_absence.cols)
            assert actual_count == expected_count, \
                f"Expected {expected_count} genomes from samples.csv, got {actual_count}"

    def test_provenance_round_trip_on_real_data(self, processed_dir):
        """RunRecord YAML round-trips on real BGCFlow data."""
        from bgclens.core.api import open_project, run
        from bgclens.core.provenance import RunRecord, hash_project

        proj = open_project(processed_dir)
        result = run(proj, "pcoa", {})
        record = RunRecord(
            project_path=str(processed_dir),
            inputs_hash=hash_project(processed_dir),
            run_spec={"method_id": "pcoa", "params": {}},
            result_summary={k: v for k, v in result.items()
                           if not k.startswith("_") and not isinstance(v, (list, dict))},
        )
        restored = RunRecord.from_yaml(record.to_yaml())
        assert restored.inputs_hash == record.inputs_hash
        assert restored.run_spec["method_id"] == "pcoa"
        assert restored.project_path == str(processed_dir)
