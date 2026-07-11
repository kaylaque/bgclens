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

# Persistent web run-record store (mirrors the CLI's --output provenance dir)
_WEB_RUNS_DIR = Path.home() / ".cache" / "bgclens" / "web-runs"


# ── Request / Response models ────────────────────────────────────────────────

class OpenProjectRequest(BaseModel):
    path: str

class RecommendRequest(BaseModel):
    path: str
    intent: str
    topic: str
    use_literature: bool = False   # default off for speed
    objective: str | None = None   # e.g. "manufacturability"

class RunRequest(BaseModel):
    path: str
    method_id: str
    params: dict[str, Any] = {}
    use_llm: bool = True

class ReportRequest(BaseModel):
    run_id: str


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
            objective=req.objective,
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
    svg_text = ""
    try:
        from bgclens.viz import render
        svg_bytes, png_bytes = render(result, proj.metadata)
        svg_b64 = base64.b64encode(svg_bytes).decode()
        png_b64 = base64.b64encode(png_bytes).decode()
        svg_text = svg_bytes.decode(errors="replace")
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

    # Capture validation signals BEFORE stripping underscore-prefixed keys
    confidence_band = result.get("_confidence_band")
    validation_checks = result.get("_validation_checks", [])
    assumption_warnings = result.get("_assumption_warnings", [])

    # Strip internal provenance keys from result before returning
    clean_result = {k: v for k, v in result.items() if not k.startswith("_")}

    # Persist a RunRecord (mirrors CLI __main__.py:140-160) so /api/report can
    # regenerate a Quarto report later. run_id = the saved record's file stem.
    try:
        from bgclens.core.provenance import RunRecord, hash_project
        record = RunRecord(
            project_path=str(req.path),
            inputs_hash=hash_project(Path(req.path)),
            run_spec={"method_id": req.method_id, "params": req.params},
            llm={"enabled": req.use_llm, "used": llm_used},
            result_summary={
                **{k: v for k, v in clean_result.items()
                   if not isinstance(v, (list, dict))},
                "interpretation": interpretation_text,
                "svg": svg_text,
            },
        )
        saved = record.save(_WEB_RUNS_DIR)
        run_id = saved.stem
    except Exception as e:
        run_id = None

    _session["last_result"] = {
        "method_id": req.method_id,
        "result": clean_result,
        "interpretation": interpretation_text,
        "run_id": run_id,
    }

    return {
        "method_id": req.method_id,
        "result": clean_result,
        "figure_svg_b64": svg_b64,
        "figure_png_b64": png_b64,
        "interpretation": interpretation_text,
        "llm_used": llm_used,
        "assumption_warnings": assumption_warnings,
        "confidence_band": confidence_band,
        "validation_checks": validation_checks,
        "run_id": run_id,
    }


@app.post("/api/report")
def api_report(req: ReportRequest):
    """Generate a Quarto report from a previously saved web run record."""
    record_path = _WEB_RUNS_DIR / f"{req.run_id}.yaml"
    if not record_path.exists():
        raise HTTPException(status_code=404, detail=f"Unknown run_id: {req.run_id}")

    from bgclens.core.provenance import RunRecord
    from bgclens.report import render as render_report

    record = RunRecord.from_yaml(record_path.read_text())
    out_dir = _WEB_RUNS_DIR / "reports" / req.run_id
    report = render_report(record, out_dir)

    html_path = None
    html_b64 = None
    if report.html_path is not None and Path(report.html_path).exists():
        html_path = str(report.html_path)
        html_b64 = base64.b64encode(Path(report.html_path).read_bytes()).decode()

    return {
        "qmd_path": str(report.qmd_path),
        "html_path": html_path,
        "html_b64": html_b64,
    }


# Labels/descriptions for the 6 analytical intents (kept from the original UI copy)
_ANALYTICAL_INTENTS: dict[str, tuple[str, str]] = {
    "enrichment":        ("Enrichment analysis",           "Which BGC classes are enriched in one group vs another?"),
    "diversity":         ("Alpha diversity",               "How diverse are BGC profiles across genomes?"),
    "ordination":        ("Ordination (PCA / PCoA)",       "Visualise genome similarity in 2D"),
    "clustering":        ("Hierarchical clustering",       "Group genomes by BGC profile similarity"),
    "comparison":        ("Group comparison (PERMANOVA)",  "Statistically test whether groups differ in BGC composition"),
    "network_structure": ("Network community detection",   "Find communities in the GCF similarity network"),
}


@app.get("/api/intents")
def api_intents():
    """Return all analysis intents, grouped Analytical vs Research questions."""
    from bgclens.core.intent import Intent, SQ_LABELS

    intents = []
    for intent in Intent:
        value = intent.value
        if value in _ANALYTICAL_INTENTS:
            label, description = _ANALYTICAL_INTENTS[value]
            group = "Analytical"
        else:
            # sq* research-question intents
            label = SQ_LABELS.get(value, value)
            description = SQ_LABELS.get(value, "")
            group = "Research questions"
        intents.append({
            "value": value,
            "label": label,
            "description": description,
            "group": group,
        })

    return {"intents": intents}


# ── Serve frontend HTML ──────────────────────────────────────────────────────
_FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
_INDEX_HTML = _FRONTEND_DIR / "index.html"

@app.get("/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
def serve_frontend():
    if _INDEX_HTML.exists():
        return HTMLResponse(_INDEX_HTML.read_text())
    return HTMLResponse("<h1>BGCLens</h1><p>Frontend not found. Run <code>bgclens web</code>.</p>")
