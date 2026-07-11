"""Integration tests for the FastAPI web surface."""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

DEMO_PROJECT = Path(__file__).parent.parent / "fixtures" / "demo_project"

@pytest.fixture
def client():
    from bgclens_web.api.main import app
    return TestClient(app)

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_intents(client):
    r = client.get("/api/intents")
    assert r.status_code == 200
    intents = r.json()["intents"]
    # 6 analytical + 7 research-question (sq*) intents
    assert len(intents) == 13
    values = [i["value"] for i in intents]
    assert "ordination" in values
    assert "enrichment" in values
    assert "sq1_inventory" in values
    assert "sq7_association" in values

    # Every item carries value/label/description/group
    for item in intents:
        assert set(item) == {"value", "label", "description", "group"}
        assert item["group"] in {"Analytical", "Research questions"}

    groups = {i["value"]: i["group"] for i in intents}
    analytical = {"enrichment", "diversity", "ordination", "clustering",
                  "comparison", "network_structure"}
    assert all(groups[v] == "Analytical" for v in analytical)
    assert len([i for i in intents if i["group"] == "Analytical"]) == 6
    assert len([i for i in intents if i["group"] == "Research questions"]) == 7
    assert groups["sq3_prioritization"] == "Research questions"

@pytest.mark.skipif(not DEMO_PROJECT.exists(), reason="Demo fixtures not found")
def test_open_project(client):
    r = client.post("/api/open", json={"path": str(DEMO_PROJECT)})
    assert r.status_code == 200
    data = r.json()
    assert data["project_name"] == "demo_project"
    assert data["genome_count"] == 8

def test_open_invalid_path(client):
    r = client.post("/api/open", json={"path": "/nonexistent/path/xyz"})
    assert r.status_code == 422

@pytest.mark.skipif(not DEMO_PROJECT.exists(), reason="Demo fixtures not found")
def test_recommend_ordination(client):
    client.post("/api/open", json={"path": str(DEMO_PROJECT)})
    r = client.post("/api/recommend", json={
        "path": str(DEMO_PROJECT),
        "intent": "ordination",
        "topic": "BGC diversity in Actinobacteria",
        "use_literature": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is True
    assert len(data["recommendations"]) >= 1

@pytest.mark.skipif(not DEMO_PROJECT.exists(), reason="Demo fixtures not found")
def test_recommend_manufacturability(client):
    client.post("/api/open", json={"path": str(DEMO_PROJECT)})
    r = client.post("/api/recommend", json={
        "path": str(DEMO_PROJECT),
        "intent": "ordination",
        "topic": "BGC diversity in Actinobacteria",
        "use_literature": False,
        "objective": "manufacturability",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is True
    recs = data["recommendations"]
    assert len(recs) >= 1
    # Every recommendation exposes an alternatives list
    for rec in recs:
        assert "alternatives" in rec
        assert isinstance(rec["alternatives"], list)
    # The manufacturability annotation is appended to the top recommendation
    manu = [
        alt for rec in recs for alt in rec["alternatives"]
        if isinstance(alt, dict) and alt.get("objective") == "manufacturability"
    ]
    assert len(manu) >= 1
    assert "tractability_score" in manu[0]


@pytest.mark.skipif(not DEMO_PROJECT.exists(), reason="Demo fixtures not found")
def test_run_pcoa(client):
    client.post("/api/open", json={"path": str(DEMO_PROJECT)})
    r = client.post("/api/run", json={
        "path": str(DEMO_PROJECT),
        "method_id": "pcoa",
        "params": {},
        "use_llm": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["method_id"] == "pcoa"
    assert len(data["figure_svg_b64"]) > 100
    assert "interpretation" in data
    assert "## Method" in data["interpretation"]
    # Validation signals surfaced (captured before underscore keys are stripped)
    assert "confidence_band" in data
    assert data["confidence_band"] in {"green", "amber", "red", None}
    assert "validation_checks" in data
    assert isinstance(data["validation_checks"], list)
    # A RunRecord was persisted; run_id is its file stem
    assert data["run_id"]


@pytest.mark.skipif(not DEMO_PROJECT.exists(), reason="Demo fixtures not found")
def test_report_from_run(client):
    client.post("/api/open", json={"path": str(DEMO_PROJECT)})
    run = client.post("/api/run", json={
        "path": str(DEMO_PROJECT),
        "method_id": "pcoa",
        "params": {},
        "use_llm": False,
    })
    run_id = run.json()["run_id"]
    assert run_id

    r = client.post("/api/report", json={"run_id": run_id})
    assert r.status_code == 200
    data = r.json()
    assert data["qmd_path"].endswith(".qmd")
    # html_path / html_b64 are null unless quarto is installed
    assert "html_path" in data
    assert "html_b64" in data


def test_report_unknown_run_id(client):
    r = client.post("/api/report", json={"run_id": "bgclens_run_deadbeef"})
    assert r.status_code == 404
