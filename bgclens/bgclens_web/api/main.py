"""Thin FastAPI wrapper over the BGCLens engine."""
from __future__ import annotations
import base64
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="BGCLens", version="0.1.0")

# ── In-memory session store (single-user, laptop tool) ──────────────────────
_session: dict[str, Any] = {}


# ── Request / Response models ────────────────────────────────────────────────

class OpenProjectRequest(BaseModel):
    path: str

class RecommendRequest(BaseModel):
    path: str
    intent: str
    topic: str
    use_literature: bool = False   # default off for speed

class RunRequest(BaseModel):
    path: str
    method_id: str
    params: dict[str, Any] = {}
    use_llm: bool = True


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/api/open")
def api_open_project(req: OpenProjectRequest):
    """Ingest a BGCFlow project and return its manifest."""
    try:
        from bgclens.core.api import open_project
        proj = open_project(Path(req.path))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    _session["project"] = proj
    _session["path"] = req.path

    m = proj.manifest
    return {
        "project_name": m.project_name,
        "source_path": str(m.source_path),
        "available_pipelines": sorted(m.available_pipelines),
        "duckdb_path": str(m.duckdb_path) if m.duckdb_path else None,
        "gcf_count": len(proj.gcf_presence_absence.rows) if proj.gcf_presence_absence else 0,
        "genome_count": len(proj.gcf_presence_absence.cols) if proj.gcf_presence_absence else 0,
        "has_counts": proj.bgc_counts is not None,
        "has_taxonomy": proj.taxonomy is not None,
        "has_network": proj.gcf_network is not None,
    }


@app.post("/api/recommend")
def api_recommend(req: RecommendRequest):
    """Recommend methods for the given intent and topic."""
    proj = _session.get("project")
    if proj is None or _session.get("path") != req.path:
        # Re-ingest if session expired or path changed
        try:
            from bgclens.core.api import open_project
            proj = open_project(Path(req.path))
            _session["project"] = proj
            _session["path"] = req.path
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    try:
        from bgclens.core.api import recommend
        from bgclens.core.intent import AnalysisRequest, Intent
        request = AnalysisRequest(
            topic=req.topic,
            intent=Intent(req.intent),
            method_hint=None,
        )
        validation, recs = recommend(proj, request, use_literature=req.use_literature)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {
        "valid": validation.valid,
        "intent": validation.intent,
        "suggestion": validation.suggestion if not validation.valid else "",
        "recommendations": [
            {
                "method_id": r.method_id,
                "method_name": r.method_name,
                "cost_class": r.cost_class,
                "cost_reason": r.cost_reason,
                "assumption_warnings": r.assumption_warnings,
                "literature_support": r.literature_support,
                "literature_citations": r.literature_citations,
                "is_recommended": r.is_recommended,
                "alternatives": r.alternatives,
            }
            for r in recs
        ],
    }


@app.post("/api/run")
def api_run(req: RunRequest):
    """Execute a method and return result + figure (SVG base64) + interpretation."""
    proj = _session.get("project")
    if proj is None or _session.get("path") != req.path:
        try:
            from bgclens.core.api import open_project
            proj = open_project(Path(req.path))
            _session["project"] = proj
            _session["path"] = req.path
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    try:
        from bgclens.core.api import run
        result = run(proj, req.method_id, req.params)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Method failed: {e}")

    # Render figure
    try:
        from bgclens.viz import render
        svg_bytes, png_bytes = render(result, proj.metadata)
        svg_b64 = base64.b64encode(svg_bytes).decode()
        png_b64 = base64.b64encode(png_bytes).decode()
    except Exception as e:
        svg_b64 = ""
        png_b64 = ""

    # Interpretation
    try:
        from bgclens.interpret import interpret
        interp = interpret(result, assumption_warnings=result.get("_assumption_warnings", []), use_llm=req.use_llm)
        interpretation_text = interp["final_text"]
        llm_used = interp["llm_used"]
    except Exception as e:
        interpretation_text = f"Interpretation unavailable: {e}"
        llm_used = False

    # Strip internal provenance keys from result before returning
    clean_result = {k: v for k, v in result.items() if not k.startswith("_")}

    _session["last_result"] = {
        "method_id": req.method_id,
        "result": clean_result,
        "interpretation": interpretation_text,
    }

    return {
        "method_id": req.method_id,
        "result": clean_result,
        "figure_svg_b64": svg_b64,
        "figure_png_b64": png_b64,
        "interpretation": interpretation_text,
        "llm_used": llm_used,
        "assumption_warnings": result.get("_assumption_warnings", []),
    }


@app.get("/api/intents")
def api_intents():
    """Return available analysis intents."""
    return {
        "intents": [
            {"value": "ordination",       "label": "Ordination (PCA / PCoA)", "description": "Visualise genome similarity in 2D"},
            {"value": "enrichment",       "label": "Enrichment analysis",      "description": "Which BGC classes are enriched in one group vs another?"},
            {"value": "diversity",        "label": "Alpha diversity",           "description": "How diverse are BGC profiles across genomes?"},
            {"value": "clustering",       "label": "Hierarchical clustering",   "description": "Group genomes by BGC profile similarity"},
            {"value": "comparison",       "label": "Group comparison (PERMANOVA)", "description": "Statistically test whether groups differ in BGC composition"},
            {"value": "network_structure","label": "Network community detection", "description": "Find communities in the GCF similarity network"},
        ]
    }


# ── Serve frontend HTML ──────────────────────────────────────────────────────
_FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
_INDEX_HTML = _FRONTEND_DIR / "index.html"

@app.get("/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
def serve_frontend():
    if _INDEX_HTML.exists():
        return HTMLResponse(_INDEX_HTML.read_text())
    return HTMLResponse("<h1>BGCLens</h1><p>Frontend not found. Run <code>bgclens web</code>.</p>")
