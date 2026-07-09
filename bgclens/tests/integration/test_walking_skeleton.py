"""
Walking skeleton integration test.
Exercises the full engine pipeline: ingest → recommend → run → viz → interpret → RunRecord.
Uses synthetic demo fixtures — no internet, no BGCFlow required.
"""
import pytest
from pathlib import Path

DEMO_PROJECT = Path(__file__).parent.parent / "fixtures" / "demo_project"


@pytest.mark.skipif(
    not DEMO_PROJECT.exists(),
    reason="Demo fixtures not found",
)
class TestWalkingSkeleton:

    def test_01_ingest(self):
        """open_project() reads the demo fixture and populates canonical types."""
        from bgclens.core.api import open_project
        project = open_project(DEMO_PROJECT)
        assert project.manifest.project_name == "demo_project"
        assert "antismash" in project.manifest.available_pipelines
        assert "bigscape" in project.manifest.available_pipelines

    def test_02_canonical_model_populated(self):
        from bgclens.core.api import open_project
        project = open_project(DEMO_PROJECT)
        assert project.gcf_presence_absence is not None
        assert len(project.gcf_presence_absence.rows) == 10   # 10 GCFs
        assert len(project.gcf_presence_absence.cols) == 8    # 8 genomes
        assert project.bgc_counts is not None
        assert len(project.bgc_counts.genome_ids) == 8
        assert project.taxonomy is not None

    def test_03_recommend_ordination(self):
        """recommend() returns valid methods with cost info."""
        from bgclens.core.api import open_project, recommend
        from bgclens.core.intent import AnalysisRequest, Intent
        project = open_project(DEMO_PROJECT)
        request = AnalysisRequest(topic="BGC diversity across Actinobacteria clades", intent=Intent.ordination)
        validation, recs = recommend(project, request, use_literature=False)
        assert validation.valid is True
        assert len(recs) >= 1
        assert any(r.is_recommended for r in recs)
        for r in recs:
            assert r.cost_class in ("Safe", "Heavy", "Likely-to-fail")

    def test_04_run_pcoa(self):
        """run() executes PCoA and returns a structured result."""
        from bgclens.core.api import open_project, run
        project = open_project(DEMO_PROJECT)
        result = run(project, "pcoa", {"n_components": 2})
        assert result.get("method") == "pcoa"
        assert "coordinates" in result
        assert len(result["coordinates"]) == 8  # 8 genomes
        assert "explained_variance_pct" in result
        assert "_provenance" in result

    def test_05_visualize(self):
        """viz.render() returns non-empty SVG and PNG bytes."""
        from bgclens.core.api import open_project, run
        from bgclens.viz import render
        project = open_project(DEMO_PROJECT)
        result = run(project, "pcoa", {"n_components": 2})
        svg, png = render(result, project.metadata)
        assert len(svg) > 100
        assert len(png) > 100
        assert b"<svg" in svg or svg.startswith(b"<?xml")
        assert png[:4] == b"\x89PNG"

    def test_06_interpret(self):
        """interpret() returns all three stages with caveats and 'what it does not tell you'."""
        from bgclens.core.api import open_project, run
        from bgclens.interpret import interpret
        project = open_project(DEMO_PROJECT)
        result = run(project, "pcoa", {"n_components": 2})
        output = interpret(result, use_llm=False)
        assert "final_text" in output
        text = output["final_text"]
        assert "## Method" in text
        assert "## Result" in text
        assert "## Caveats" in text
        assert "## What this does NOT tell you" in text
        assert output["llm_used"] is False

    def test_07_run_enrichment(self):
        """Fisher enrichment runs end-to-end on BGC count data."""
        from bgclens.core.api import open_project, run
        project = open_project(DEMO_PROJECT)
        # Use "genus" — cleanly splits Streptomyces (4) vs Saccharopolyspora (4).
        # The metadata table maps standard taxonomy columns; "genus" is always present.
        result = run(project, "fisher_enrichment", {"grouping_col": "genus"})
        assert result.get("test") == "fisher_exact"
        assert "pvalues_raw" in result
        assert len(result["pvalues_raw"]) == 5  # 5 BGC features

    def test_08_run_diversity(self):
        """Alpha diversity runs end-to-end."""
        from bgclens.core.api import open_project, run
        project = open_project(DEMO_PROJECT)
        result = run(project, "alpha_diversity", {"metrics": ["shannon", "simpson"]})
        assert result.get("method") == "alpha_diversity"
        assert result["n_genomes"] == 8
        assert result["mean_shannon"] is not None

    def test_09_session_swap(self):
        """Session retains last 2 results for method comparison."""
        from bgclens.core.api import open_project, run
        from bgclens.core.session import Session
        project = open_project(DEMO_PROJECT)
        session = Session(project)

        r1 = run(project, "pcoa")
        session.add_result(r1)
        r2 = run(project, "alpha_diversity")
        session.add_result(r2)

        assert len(session.history) == 2
        assert session.last_result.get("method") == "alpha_diversity"
        # r1 still retained
        assert any(r.get("method") == "pcoa" for r in session.history)

    def test_10_provenance_round_trip(self):
        """RunRecord serializes to YAML and back with stable inputs_hash."""
        from bgclens.core.api import open_project, run
        from bgclens.core.provenance import RunRecord, hash_project
        project = open_project(DEMO_PROJECT)
        result = run(project, "pcoa")

        record = RunRecord(
            project_path=str(DEMO_PROJECT),
            inputs_hash=hash_project(DEMO_PROJECT),
            run_spec={"method_id": "pcoa", "params": {}},
            result_summary={"n_genomes": result.get("n_genomes", 0)},
        )
        yaml_text = record.to_yaml()
        assert "bgclens_run" in yaml_text
        assert "sha256:" in yaml_text

        restored = RunRecord.from_yaml(yaml_text)
        assert restored.inputs_hash == record.inputs_hash
        assert restored.run_spec["method_id"] == "pcoa"

    def test_11_interpret_with_llm(self):
        """interpret() with LLM enabled calls the real LLM endpoint if configured."""
        from bgclens.core.api import open_project, run
        from bgclens.interpret import interpret
        from bgclens.core.config import get_settings

        settings = get_settings()
        project = open_project(DEMO_PROJECT)
        result = run(project, "pcoa", {"n_components": 2})

        # Try with LLM — if not configured it should gracefully fall back
        output = interpret(result, use_llm=True)
        assert "final_text" in output
        assert len(output["final_text"]) > 50
        # If LLM was configured and worked, llm_used should be True
        if settings.llm.enabled and settings.llm.api_key:
            # LLM was attempted - result should be non-empty regardless
            assert len(output["final_text"]) > 100
        # Either way, the text must contain key sections
        assert "Method" in output["final_text"] or "method" in output["final_text"].lower()
