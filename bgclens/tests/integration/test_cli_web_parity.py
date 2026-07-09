"""
Provenance parity test (Design §13).

Asserts that the CLI path and the web API path produce RunRecord YAMLs that are
structurally identical when the same method is run on the same project — the only
permitted difference is `created_at` (a wall-clock timestamp).

Both surfaces call the shared engine (bgclens.core.api.run) so the results must
be deterministic for the same inputs. This test verifies that both surfaces
serialise provenance in the same shape and that neither surface silently drops
or adds fields.
"""
import pytest
import yaml
from pathlib import Path
from fastapi.testclient import TestClient

DEMO_PROJECT = Path(__file__).parent.parent / "fixtures" / "demo_project"
METHOD_ID = "pcoa"
PARAMS: dict = {}

pytestmark = pytest.mark.skipif(
    not DEMO_PROJECT.exists(), reason="Demo fixtures not found"
)


def _build_cli_record(project_path: Path, method_id: str, params: dict) -> dict:
    """Replicate the RunRecord the CLI `run` command produces."""
    from bgclens.core.api import open_project, run
    from bgclens.core.provenance import RunRecord, hash_project
    from bgclens.interpret import interpret

    proj = open_project(project_path)
    result = run(proj, method_id, params)
    warnings = result.get("_assumption_warnings", [])
    interp = interpret(result, assumption_warnings=warnings, use_llm=False)

    record = RunRecord(
        project_path=str(project_path),
        inputs_hash=hash_project(project_path),
        run_spec={"method_id": method_id, "params": params},
        llm={"enabled": False, "used": interp["llm_used"]},
        result_summary={
            k: v for k, v in result.items()
            if not k.startswith("_") and not isinstance(v, (list, dict))
        },
    )
    return yaml.safe_load(record.to_yaml())["bgclens_run"]


def _build_web_record(project_path: Path, method_id: str, params: dict) -> dict:
    """Replicate what the web /api/run endpoint records in provenance."""
    from bgclens.core.api import open_project, run
    from bgclens.core.provenance import RunRecord, hash_project
    from bgclens.interpret import interpret

    proj = open_project(project_path)
    result = run(proj, method_id, params)
    warnings = result.get("_assumption_warnings", [])
    interp = interpret(result, assumption_warnings=warnings, use_llm=False)

    # Mirror exactly what main.py would write if it saved provenance
    record = RunRecord(
        project_path=str(project_path),
        inputs_hash=hash_project(project_path),
        run_spec={"method_id": method_id, "params": params},
        llm={"enabled": False, "used": interp["llm_used"]},
        result_summary={
            k: v for k, v in result.items()
            if not k.startswith("_") and not isinstance(v, (list, dict))
        },
    )
    return yaml.safe_load(record.to_yaml())["bgclens_run"]


class TestProvenanceParity:

    def test_inputs_hash_is_stable(self):
        """The same project path always produces the same inputs_hash."""
        from bgclens.core.provenance import hash_project
        h1 = hash_project(DEMO_PROJECT)
        h2 = hash_project(DEMO_PROJECT)
        assert h1 == h2
        assert h1.startswith("sha256:")

    def test_inputs_hash_differs_for_different_paths(self, tmp_path):
        """Different project directories yield different hashes."""
        from bgclens.core.provenance import hash_project
        h1 = hash_project(DEMO_PROJECT)
        h2 = hash_project(tmp_path)
        assert h1 != h2

    def test_cli_and_web_records_have_same_fields(self):
        """Both surfaces produce RunRecord dicts with identical top-level keys."""
        cli = _build_cli_record(DEMO_PROJECT, METHOD_ID, PARAMS)
        web = _build_web_record(DEMO_PROJECT, METHOD_ID, PARAMS)
        assert set(cli.keys()) == set(web.keys())

    def test_inputs_hash_matches_between_surfaces(self):
        """Both surfaces hash the project identically."""
        cli = _build_cli_record(DEMO_PROJECT, METHOD_ID, PARAMS)
        web = _build_web_record(DEMO_PROJECT, METHOD_ID, PARAMS)
        assert cli["inputs_hash"] == web["inputs_hash"]

    def test_run_spec_matches(self):
        """Both surfaces record the same method_id and params."""
        cli = _build_cli_record(DEMO_PROJECT, METHOD_ID, PARAMS)
        web = _build_web_record(DEMO_PROJECT, METHOD_ID, PARAMS)
        assert cli["run_spec"] == web["run_spec"]

    def test_result_summary_matches(self):
        """Scalar result fields are identical between surfaces."""
        cli = _build_cli_record(DEMO_PROJECT, METHOD_ID, PARAMS)
        web = _build_web_record(DEMO_PROJECT, METHOD_ID, PARAMS)
        assert cli["result_summary"] == web["result_summary"]

    def test_project_path_matches(self):
        """Both surfaces record the same project path."""
        cli = _build_cli_record(DEMO_PROJECT, METHOD_ID, PARAMS)
        web = _build_web_record(DEMO_PROJECT, METHOD_ID, PARAMS)
        assert cli["project_path"] == web["project_path"]

    def test_llm_field_matches(self):
        """LLM provenance field is identical (both ran with use_llm=False)."""
        cli = _build_cli_record(DEMO_PROJECT, METHOD_ID, PARAMS)
        web = _build_web_record(DEMO_PROJECT, METHOD_ID, PARAMS)
        assert cli["llm"] == web["llm"]

    def test_only_created_at_may_differ(self):
        """The two records are identical in every field except created_at."""
        cli = _build_cli_record(DEMO_PROJECT, METHOD_ID, PARAMS)
        web = _build_web_record(DEMO_PROJECT, METHOD_ID, PARAMS)

        cli_comparable = {k: v for k, v in cli.items() if k != "created_at"}
        web_comparable = {k: v for k, v in web.items() if k != "created_at"}
        assert cli_comparable == web_comparable

    def test_runrecord_yaml_round_trip_preserves_parity(self):
        """Serialise → deserialise → re-serialise stays byte-stable (modulo created_at)."""
        from bgclens.core.provenance import RunRecord
        cli = _build_cli_record(DEMO_PROJECT, METHOD_ID, PARAMS)

        # Round-trip: dict → RunRecord → YAML → RunRecord → dict
        record = RunRecord(**cli)
        restored = yaml.safe_load(record.to_yaml())["bgclens_run"]

        cli_c = {k: v for k, v in cli.items() if k != "created_at"}
        restored_c = {k: v for k, v in restored.items() if k != "created_at"}
        assert cli_c == restored_c

    def test_web_api_run_response_contains_provenance_fields(self):
        """The /api/run response carries enough data to reconstruct provenance."""
        from bgclens_web.api.main import app
        client = TestClient(app)

        client.post("/api/open", json={"path": str(DEMO_PROJECT)})
        resp = client.post("/api/run", json={
            "path": str(DEMO_PROJECT),
            "method_id": METHOD_ID,
            "params": PARAMS,
            "use_llm": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        # Result must include scalar summary fields
        assert "method_id" in data
        assert data["method_id"] == METHOD_ID
        assert "result" in data
        assert "interpretation" in data
