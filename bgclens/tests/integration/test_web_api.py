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
    assert len(intents) == 6
    values = [i["value"] for i in intents]
    assert "ordination" in values
    assert "enrichment" in values

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
