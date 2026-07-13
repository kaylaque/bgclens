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

_run_records: dict[str, Any] = {}  # run_id -> RunRecord, in-memory cache


def _get_project(path: str):
    """Load project from session cache or re-ingest."""
    proj = _session.get("project")
    if proj is None or _session.get("path") != path:
        from bgclens.core.api import open_project
        from pathlib import Path as _Path
        proj = open_project(_Path(path))
        _session["project"] = proj
        _session["path"] = path
    return proj


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


# ── New v2 request/response models ──────────────────────────────────────────

class RunBatchRequest(BaseModel):
    path: str
    method_ids: list[str] = ["alpha_diversity", "fisher_exact"]
    cluster_ids: list[str] | None = None  # None = smoke round (first 3)
    use_llm: bool = True

class LockReportRequest(BaseModel):
    run_ids: list[str]
    wrap_rocrate: bool = False

class ChatRequest(BaseModel):
    path: str
    run_ids: list[str] = []
    message: str
    history: list[dict] = []   # list of {role, content}


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


# ── New v2 endpoints ─────────────────────────────────────────────────────────

@app.get("/api/clusters")
def api_clusters(path: str):
    """List cluster profiles for a BGCFlow project."""
    from bgclens.core.api import open_project
    from bgclens.core.clusters import list_clusters
    try:
        proj = _get_project(path)
        clusters = list_clusters(proj)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "clusters": [
            {
                "cluster_id": c.cluster_id,
                "gcf_id": c.gcf_id,
                "cluster_type": c.cluster_type,
                "organism": c.organism,
                "novelty_band": c.novelty_band,
                "novelty_distance": c.novelty_distance,
            }
            for c in clusters
        ]
    }


@app.get("/api/kb")
def api_kb(path: str):
    """List Knowledge Base objects available for @mention in chat."""
    from bgclens.core.clusters import list_clusters
    try:
        proj = _get_project(path)
        clusters = list_clusters(proj)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    objects = []
    for c in clusters:
        objects.append({"id": c.cluster_id, "type": "cluster", "label": f"{c.cluster_id} ({c.cluster_type})"})

    # Methods
    for method_id, (label, _) in _ANALYTICAL_INTENTS.items():
        objects.append({"id": method_id, "type": "method", "label": label})

    # Cached report sections from last run
    for run_id, rec in _run_records.items():
        rs = rec.result_summary or {}
        method_id_val = (rec.run_spec or {}).get("method_id", "")
        if method_id_val:
            objects.append({"id": f"section_{run_id[:8]}", "type": "report_section",
                           "label": f"Report: {method_id_val}"})

    return {"objects": objects}


@app.post("/api/run-batch")
async def api_run_batch(req: RunBatchRequest):
    """Run multiple methods across clusters (parallel). Returns JSON array of results."""
    from bgclens.core.api import run_batch
    import asyncio

    try:
        proj = _get_project(req.path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        results = await run_batch(
            proj,
            method_ids=req.method_ids,
            cluster_ids=req.cluster_ids,
            use_llm=req.use_llm,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Batch run failed: {e}")

    # Save RunRecords for each result
    run_ids = []
    for res in results:
        try:
            from bgclens.core.provenance import RunRecord, hash_project
            from pathlib import Path
            cluster_id = res.get("_cluster_id", "")
            method_id = res.get("method", res.get("_method_id", "unknown"))
            record = RunRecord(
                project_path=req.path,
                inputs_hash=hash_project(Path(req.path)),
                run_spec={"method_id": method_id, "cluster_id": cluster_id, "params": {}},
                llm={"enabled": req.use_llm},
                result_summary={k: v for k, v in res.items()
                               if not k.startswith("_") and not isinstance(v, (list, dict))},
            )
            saved = record.save(_WEB_RUNS_DIR)
            run_id = saved.stem
            _run_records[run_id] = record
            run_ids.append(run_id)
        except Exception:
            pass

    return {"results": results, "run_ids": run_ids}


@app.post("/api/report/lock")
def api_report_lock(req: LockReportRequest):
    """Render a batch report, lock it, and optionally wrap in RO-Crate."""
    from bgclens.core.provenance import RunRecord
    from bgclens.report import render as render_report
    from pathlib import Path
    import base64

    records = []
    for run_id in req.run_ids:
        record_path = _WEB_RUNS_DIR / f"{run_id}.yaml"
        if record_path.exists():
            try:
                rec = RunRecord.from_yaml(record_path.read_text())
                records.append(rec)
            except Exception:
                pass

    if not records:
        raise HTTPException(status_code=404, detail="No valid run records found for provided run_ids")

    # Render the first record as the report base (batch QMD composition)
    try:
        from bgclens.model import BatchReport
        from bgclens.interpret.reduce import reduce_summary
        from bgclens.report.quarto import render_batch

        # Build cluster comparison
        comparison = {}
        for rec in records:
            rs = rec.result_summary or {}
            cid = (rec.run_spec or {}).get("cluster_id", "unknown")
            mid = (rec.run_spec or {}).get("method_id", "unknown")
            key = f"{mid}@{cid}"
            comparison[key] = rs.get("interpretation", f"{mid} completed")

        # Use first record's project name
        proj_name = Path(records[0].project_path).name if records else "BGCLens"
        summary_text = reduce_summary([r.result_summary or {} for r in records])

        batch = BatchReport(
            project_name=proj_name,
            records=records,
            summary=summary_text,
            cluster_comparison=comparison,
        )
        out_dir = _WEB_RUNS_DIR / "reports" / "batch"
        report = render_batch(batch, out_dir)

    except Exception as e:
        # Fallback to single-record render
        report = render_report(records[0], _WEB_RUNS_DIR / "reports" / req.run_ids[0])

    # Lock the report
    locked_path = None
    rocrate_path = None
    try:
        if report.qmd_path and report.qmd_path.exists():
            # Use first record for locking metadata
            rec0 = records[0]
            locked_path = rec0.lock(report.qmd_path)
            rec0.save(_WEB_RUNS_DIR)  # re-save with locked=True
    except Exception as e:
        locked_path = report.qmd_path

    # RO-Crate wrap
    if req.wrap_rocrate and locked_path:
        try:
            from bgclens.report.rocrate import wrap
            crate = wrap(records[0], extra_files=[])
            rocrate_path = str(crate) if crate else None
        except Exception:
            rocrate_path = None

    html_b64 = None
    html_path = None
    if report.html_path and Path(report.html_path).exists():
        html_path = str(report.html_path)
        html_b64 = base64.b64encode(Path(report.html_path).read_bytes()).decode()

    return {
        "qmd_path": str(report.qmd_path) if report.qmd_path else None,
        "locked_path": str(locked_path) if locked_path else None,
        "html_path": html_path,
        "html_b64": html_b64,
        "rocrate_path": rocrate_path,
        "note": report.note,
    }


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    """Single chat turn with retrieval-augmented context over project + run records."""
    from bgclens.interpret.chat import chat
    from bgclens.interpret.mentions import parse
    from bgclens.model import Turn
    from bgclens.core.provenance import RunRecord
    from pathlib import Path

    try:
        proj = _get_project(req.path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Load run records
    records = []
    for run_id in req.run_ids:
        record_path = _WEB_RUNS_DIR / f"{run_id}.yaml"
        if record_path.exists():
            try:
                records.append(RunRecord.from_yaml(record_path.read_text()))
            except Exception:
                pass

    # Parse history
    history: list[Turn] = []
    for h in req.history[-6:]:
        role = h.get("role", "user")
        content = h.get("content", "")
        if role in ("user", "assistant") and content:
            history.append(Turn(role=role, content=content))

    # Build KB whitelist from clusters
    try:
        from bgclens.core.clusters import list_clusters
        clusters = list_clusters(proj)
        whitelist = {c.cluster_id for c in clusters}
    except Exception:
        whitelist = set()

    # Parse mentions from message
    mentions = parse(req.message, whitelist=whitelist if whitelist else None)

    turn = chat(proj, records, history, req.message, mentions)

    return {
        "reply": turn.content,
        "mentions_resolved": [m.object_id for m in mentions],
        "role": turn.role,
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
