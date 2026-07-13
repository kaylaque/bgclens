"""Thin FastAPI wrapper over the BGCLens engine."""
from __future__ import annotations
import base64
import logging
import logging.handlers
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Logging ──────────────────────────────────────────────────────────────────
# Configure before uvicorn starts so our format wins for bgclens.web logger
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter(
    fmt="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
))
_log = logging.getLogger("bgclens.web")
_log.setLevel(logging.INFO)
_log.addHandler(_handler)
_log.propagate = False   # don't double-print via uvicorn root handler

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
    method_ids: list[str] = ["alpha_diversity", "fisher_enrichment"]
    cluster_ids: list[str] | None = None  # None = smoke round (first 3)
    use_llm: bool = True


class LiteratureSearchRequest(BaseModel):
    query: str
    max_results: int = 8

class ExtractMethodsRequest(BaseModel):
    papers: list[dict] = []    # preferred: [{title, abstract, doi, pmid, url, source}]
    abstracts: list[str] = []  # legacy fallback
    titles: list[str] = []     # legacy fallback

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

    _log.info("⚙️  [run-batch] methods=%s path=%s llm=%s",
              req.method_ids, Path(req.path).name, req.use_llm)

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

    _log.info("  ✅ Batch complete: %d result(s) — adding interpretations...", len(results))

    # Add LLM interpretation to each result
    for res in results:
        if isinstance(res, dict) and "_error" not in res:
            try:
                from bgclens.interpret import interpret
                interp = interpret(res, assumption_warnings=res.get("_assumption_warnings", []), use_llm=req.use_llm)
                res["interpretation"] = interp["final_text"]
                res["llm_used"] = interp["llm_used"]
            except Exception:
                pass
            try:
                from bgclens.viz import render as render_viz
                svg_bytes, png_bytes = render_viz(res, getattr(proj, 'metadata', None))
                res["_svg"] = svg_bytes.decode(errors="replace")
            except Exception:
                res["_svg"] = ""

    # Save RunRecords for each result
    run_ids = []
    errors = [r for r in results if isinstance(r, dict) and "_error" in r]
    if errors:
        _log.warning("  ⚠️  %d error(s) in batch results", len(errors))
    _log.info("  💾 Saving %d run record(s)...", len(results) - len(errors))

    for res in results:
        try:
            from bgclens.core.provenance import RunRecord, hash_project
            cluster_id = res.get("_cluster_id", "")
            method_id = res.get("method", res.get("_method_id", "unknown"))
            record = RunRecord(
                project_path=req.path,
                inputs_hash=hash_project(Path(req.path)),
                run_spec={"method_id": method_id, "cluster_id": cluster_id, "params": {}},
                llm={"enabled": req.use_llm},
                result_summary={
                    **{k: v for k, v in res.items()
                       if not k.startswith("_") and not isinstance(v, (list, dict))},
                    "svg": res.get("_svg", ""),
                },
            )
            saved = record.save(_WEB_RUNS_DIR)
            run_id = saved.stem
            _run_records[run_id] = record
            run_ids.append(run_id)
        except Exception:
            pass

    _log.info("  🏁 run-batch done: %d run IDs saved", len(run_ids))
    return {"results": results, "run_ids": run_ids}


@app.post("/api/report/lock")
def api_report_lock(req: LockReportRequest):
    """Render a batch report, lock it, and optionally wrap in RO-Crate."""
    from bgclens.core.provenance import RunRecord
    from bgclens.report import render as render_report
    from pathlib import Path
    import base64

    _log.info("📊 [report/lock] %d run IDs, rocrate=%s", len(req.run_ids), req.wrap_rocrate)

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

    _log.info("  📝 Rendering report for %d record(s)...", len(records))

    # Render the first record as the report base (batch QMD composition)
    try:
        from bgclens.model import BatchReport
        from bgclens.interpret.reduce import reduce_summary
        from bgclens.report import render_batch

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
        run_set_key = "_".join(sorted(req.run_ids))[:32]
        out_dir = _WEB_RUNS_DIR / "reports" / f"batch_{run_set_key}"
        report = render_batch(batch, out_dir)

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("render_batch failed: %s", e)
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
        _log.info("  ✅ Report HTML ready: %s", html_path)
    else:
        _log.info("  ✅ Report QMD only (no HTML rendered): %s", report.qmd_path)

    return {
        "qmd_path": str(report.qmd_path) if report.qmd_path else None,
        "locked_path": str(locked_path) if locked_path else None,
        "html_path": html_path,
        "html_b64": html_b64,
        "rocrate_path": rocrate_path,
        "note": report.note,
    }


@app.post("/api/literature")
async def api_literature(req: LiteratureSearchRequest):
    """Search EuropePMC, PubMed, and bioRxiv for papers matching a query."""
    import asyncio
    import concurrent.futures

    _log.info("📚 [literature] query=%r max=%d", req.query[:80], req.max_results)

    def _search_sync():
        try:
            from bgclens.literature.providers import search_all
            return search_all(req.query, max_results=req.max_results)
        except Exception as e:
            _log.warning("  search_all failed (%s) — EuropePMC only fallback", e)
            try:
                from bgclens.literature.providers.europepmc import _search_works, _to_citation
                works = _search_works(req.query, per_page=req.max_results + 2)
                cits = [_to_citation(w) for w in works[:req.max_results]]
                return [
                    {"title": c.title, "authors": c.authors, "year": c.year,
                     "doi": c.doi, "abstract": c.abstract_snippet,
                     "url": f"https://doi.org/{c.doi}" if c.doi else None,
                     "source": "europepmc"}
                    for c in cits
                ]
            except Exception:
                return []

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, _search_sync)

    sources = list({r.get("source", "?") for r in results})
    _log.info("  ✅ %d results from: %s", len(results), ", ".join(sorted(sources)))

    return {
        "query": req.query,
        "total": len(results),
        "sources_searched": ["europepmc", "pubmed", "biorxiv"],
        "results": results,
    }


_BGCLENS_KEYWORD_MAP: dict[str, list[str]] = {
    "alpha_diversity": ["shannon", "simpson", "alpha diversity", "species richness", "diversity index"],
    "fisher_enrichment": ["fisher", "enrichment", "chi-square", "overrepresent", "hypergeometric"],
    "hierarchical_clustering": ["hierarchical cluster", "hclust", "dendrogram", "ward", "agglomerative"],
    "pcoa": ["pcoa", "principal coordinates", "beta diversity", "bray-curtis", "unifrac"],
    "pca": ["pca", "principal component", "dimensionality reduction", "t-sne", "umap", "tsne"],
    "permanova": ["permanova", "adonis", "permutational anova", "multivariate permutation"],
    "louvain_community": ["louvain", "community detection", "network cluster", "modularity", "graph partition"],
    "manufacturability": ["expression", "heterologous", "chassis", "e. coli", "synthetic biology", "codon optim"],
}


def _infer_bgclens_id(method_name: str, intention: str) -> str | None:
    text = (method_name + " " + intention).lower()
    for bgclens_id, keywords in _BGCLENS_KEYWORD_MAP.items():
        if any(kw in text for kw in keywords):
            return bgclens_id
    return None


def _scrape_paper_text(url: str = "", doi: str = "", pmid: str = "") -> tuple[str, str]:
    """Attempt to fetch and clean full paper text from open-access sources.

    Returns (cleaned_text[:6000], final_url) or ("", "") if inaccessible.
    Tries candidates in order: preprint servers first (always OA), then
    EuropePMC viewer, then DOI redirect, then original URL.
    """
    try:
        import httpx
        import re as _re
    except ImportError:
        return "", ""

    HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BGCLens/0.1 research bot)"}
    candidates: list[str] = []

    # Preprints — always open access
    if doi:
        doi_lower = doi.lower()
        if "biorxiv" in doi_lower or "10.1101" in doi_lower:
            candidates.append(f"https://www.biorxiv.org/content/{doi}v1.full")
        if "medrxiv" in doi_lower:
            candidates.append(f"https://www.medrxiv.org/content/{doi}v1.full")

    # EuropePMC viewer — open access for many PMC papers
    if pmid:
        candidates.append(f"https://europepmc.org/article/MED/{pmid}")

    # DOI redirect (may land on OA publisher or paywall)
    if doi:
        candidates.append(f"https://doi.org/{doi}")

    # Original URL from provider (e.g. abstract page)
    if url and url not in candidates:
        candidates.append(url)

    for candidate_url in candidates[:5]:
        try:
            _log.info("    🌐 Checking: %s", candidate_url[:80])
            head = httpx.head(candidate_url, timeout=5.0, follow_redirects=True, headers=HEADERS)
            final_url = str(head.url)
            ctype = head.headers.get("content-type", "")

            if head.status_code != 200 or any(x in ctype for x in ("pdf", "octet", "zip")):
                _log.info("    🚫 Skipped (%s %s)", head.status_code, ctype[:30])
                continue

            r = httpx.get(final_url, timeout=12.0, follow_redirects=True, headers=HEADERS)
            if r.status_code != 200 or len(r.text) < 400:
                continue

            html = r.text
            # Remove non-content blocks
            for tag in ("script", "style", "nav", "header", "footer", "aside",
                        "figure", "figcaption", "noscript"):
                html = _re.sub(
                    f"<{tag}[^>]*>.*?</{tag}>", "", html,
                    flags=_re.DOTALL | _re.IGNORECASE,
                )
            text = _re.sub(r"<[^>]+>", " ", html)
            text = _re.sub(r"\s+", " ", text).strip()

            if len(text) < 400:
                _log.info("    ⚠️  Too short after cleaning (%d chars)", len(text))
                continue

            _log.info("    📄 Scraped %d chars from %s", len(text), final_url[:70])
            return text[:6000], final_url

        except Exception as exc:
            _log.debug("    scrape error for %s: %s", candidate_url[:60], exc)
            continue

    return "", ""


def _fetch_abstract_epmc(doi: str = "", pmid: str = "") -> str:
    """Fetch abstract when the provider didn't return one.

    - PMID  → NCBI efetch (reliable for PubMed papers)
    - DOI   → EuropePMC search (good for preprints / OA papers)
    """
    try:
        import httpx
        if pmid:
            r = httpx.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                params={"db": "pubmed", "id": pmid, "rettype": "medline", "retmode": "text"},
                timeout=6.0,
            )
            if r.status_code == 200:
                import re as _re
                # MEDLINE format: "AB  - text\n      continuation" → extract AB field
                m_ab = _re.search(
                    r"^AB  - (.+?)(?=^[A-Z]{2,4}  -|\Z)",
                    r.text, _re.MULTILINE | _re.DOTALL
                )
                if m_ab:
                    abstract = " ".join(m_ab.group(1).replace("\n      ", " ").split())
                    return abstract

        if doi:
            r = httpx.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                params={"query": f'DOI:"{doi}"', "format": "json",
                        "resultType": "core", "pageSize": "1"},
                timeout=5.0,
            )
            if r.status_code == 200:
                hits = r.json().get("resultList", {}).get("result", [])
                if hits:
                    return hits[0].get("abstractText", "") or ""
    except Exception:
        pass
    return ""


_EXTRACT_PROMPT = """\
You are a bioinformatics expert specialising in biosynthetic gene cluster (BGC) genomics.

Analyse the content below and extract EVERY analytical or computational method mentioned, applied, or implied.
Rules:
- Extract ALL methods — standard ones (PCA, ANOVA, Shannon diversity) AND domain-specific or novel ones
- One paper can yield multiple methods — list ALL of them
- For each method provide a CONCISE but complete entry

Content:
{block}

Return ONLY a valid JSON array (no markdown, no backticks, no explanation):
[
  {{
    "method_name": "Shannon Diversity Index",
    "intention": "Quantifies species diversity within a sample using information entropy.",
    "insight": "Reveals how evenly BGC families are distributed across microbial communities.",
    "paper_title": "exact paper title this came from"
  }}
]

If truly no methods are discernible, return [].
"""


def _keyword_fallback(enriched: list[dict], note: str = "") -> list[dict]:
    combined = " ".join((p["title"] + " " + p["abstract"]) for p in enriched).lower()
    found = []
    for bgclens_id, keywords in _BGCLENS_KEYWORD_MAP.items():
        for kw in keywords:
            if kw in combined:
                source_title = next(
                    (p["title"] for p in enriched
                     if kw in (p["title"] + p["abstract"]).lower()), ""
                )
                found.append({
                    "method_name": bgclens_id.replace("_", " ").title(),
                    "intention": f"Identified via keyword match{' (' + note + ')' if note else ''}.",
                    "insight": "Potentially relevant to BGC analysis.",
                    "paper_title": source_title,
                    "bgclens_id": bgclens_id,
                })
                break
    return found


@app.post("/api/literature/extract-methods")
def api_extract_methods(req: ExtractMethodsRequest):
    """Extract ALL analytical methods from papers — with full-paper scrape fallback.

    Flow:
    1. Enrich missing abstracts via NCBI efetch / EuropePMC
    2. LLM extraction from abstracts
    3. If empty → scrape full paper text (open-access sources) → LLM again
    4. If still empty → keyword-matching fallback
    """
    import json
    import re

    from bgclens.core.config import get_settings

    settings = get_settings()
    llm = settings.llm

    # ── Normalise input ───────────────────────────────────────────────────────
    if req.papers:
        raw_papers = req.papers
    else:
        raw_papers = [
            {
                "title": req.titles[i] if i < len(req.titles) else "",
                "abstract": req.abstracts[i] if i < len(req.abstracts) else "",
            }
            for i in range(len(req.abstracts))
        ]

    _log.info("🔬 [extract-methods] %d paper(s) selected", len(raw_papers))

    # ── Enrich abstracts ──────────────────────────────────────────────────────
    enriched: list[dict] = []
    for p in raw_papers[:8]:
        title    = (p.get("title")    or "").strip()
        abstract = (p.get("abstract") or "").strip()
        doi      = (p.get("doi")      or "").strip()
        pmid     = str(p.get("pmid")  or "").strip()
        url      = (p.get("url")      or "").strip()
        source   = (p.get("source")   or "").strip()

        if not abstract and (doi or pmid):
            _log.info("  🔍 Fetching abstract for: %s", title[:55])
            fetched = _fetch_abstract_epmc(doi=doi, pmid=pmid)
            if fetched:
                abstract = fetched
                _log.info("  ✅ Got abstract (%d chars)", len(abstract))
            else:
                _log.info("  ⚠️  No abstract available")

        enriched.append({
            "title": title, "abstract": abstract,
            "doi": doi, "pmid": pmid, "url": url, "source": source,
        })

    if not any(p["title"] or p["abstract"] for p in enriched):
        _log.info("  ⚠️  No usable content — returning empty")
        return {"methods": []}

    # ── Build papers block ────────────────────────────────────────────────────
    def _build_block(papers: list[dict], use_full_text: dict[int, str] | None = None) -> str:
        block = ""
        for i, p in enumerate(papers):
            block += f"\n---\nPaper {i+1}: {p['title']}\n"
            ft = (use_full_text or {}).get(i, "")
            if ft:
                block += f"Full text (truncated):\n{ft}\n"
            elif p["abstract"]:
                block += f"Abstract: {p['abstract']}\n"
            else:
                block += "(abstract not available — infer from title only)\n"
        return block

    # ── No LLM: keyword fallback ──────────────────────────────────────────────
    if not llm.enabled or not llm.api_key:
        _log.info("  ⚠️  LLM disabled — using keyword matching")
        methods = _keyword_fallback(enriched, note="LLM disabled")
        _log.info("  📋 Keyword fallback: %d methods", len(methods))
        return {"methods": methods}

    # ── LLM helper ────────────────────────────────────────────────────────────
    import openai
    client = openai.OpenAI(base_url=llm.base_url, api_key=llm.api_key)

    def _call_llm(block: str, label: str = "abstracts", max_tokens: int = 1800) -> list[dict]:
        _log.info("  🤖 LLM call [%s] → %s (%d chars)...", label, llm.model, len(block))
        try:
            resp = client.chat.completions.create(
                model=llm.model,
                messages=[{"role": "user", "content": _EXTRACT_PROMPT.format(block=block)}],
                temperature=0.1,
                max_tokens=max_tokens,
            )
            raw = resp.choices[0].message.content.strip()

            # Strategy 1: complete JSON array
            m_arr = re.search(r"\[.*\]", raw, re.DOTALL)
            if m_arr:
                try:
                    parsed = json.loads(m_arr.group(0))
                    _log.info("  ✅ LLM returned %d method(s) (full array)", len(parsed))
                    return parsed
                except json.JSONDecodeError:
                    pass

            # Strategy 2: extract individual complete objects (handles truncated array)
            objects = re.findall(r"\{[^{}]+\}", raw, re.DOTALL)
            parsed = []
            required = {"method_name", "intention", "insight", "paper_title"}
            for obj_str in objects:
                try:
                    obj = json.loads(obj_str)
                    if required.issubset(obj.keys()):
                        parsed.append(obj)
                except json.JSONDecodeError:
                    pass
            if parsed:
                _log.info("  ✅ LLM returned %d method(s) (partial recovery)", len(parsed))
                return parsed

            _log.warning("  ⚠️  LLM returned unparseable content (len=%d)", len(raw))
            return []
        except Exception as exc:
            _log.warning("  ⚠️  LLM call failed: %s", exc)
            return []

    # ── Round 1: extract from abstracts ──────────────────────────────────────
    methods = _call_llm(_build_block(enriched), label="abstracts")

    # ── Round 2: scrape full paper text if round 1 yielded nothing ───────────
    if not methods:
        _log.info("  📭 No methods from abstracts — attempting full paper scrape...")
        full_texts: dict[int, str] = {}

        for i, p in enumerate(enriched):
            text, final_url = _scrape_paper_text(
                url=p["url"], doi=p["doi"], pmid=p["pmid"]
            )
            if text:
                full_texts[i] = text
            else:
                _log.info("    🚫 Paper %d not accessible: %s", i + 1,
                          (p["url"] or p["doi"] or p["pmid"] or p["title"])[:60])

        if full_texts:
            _log.info("  📚 Scraped %d / %d papers — calling LLM on full text...",
                      len(full_texts), len(enriched))
            methods = _call_llm(
                _build_block(enriched, use_full_text=full_texts),
                label="full-text",
                max_tokens=1600,
            )
        else:
            _log.info("  📭 No papers were accessible for full-text scraping")

    # ── Annotate with bgclens_id ──────────────────────────────────────────────
    for meth in methods:
        meth["bgclens_id"] = _infer_bgclens_id(
            meth.get("method_name", ""), meth.get("intention", "")
        )

    # ── Round 3: keyword fallback if both LLM rounds returned nothing ─────────
    if not methods:
        _log.info("  📋 Both LLM rounds empty — keyword fallback")
        methods = _keyword_fallback(enriched)

    _log.info("  🏁 Returning %d total method(s)", len(methods))
    return {"methods": methods}


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    """Single chat turn with retrieval-augmented context over project + run records."""
    from bgclens.interpret.chat import chat
    from bgclens.interpret.mentions import parse
    from bgclens.model import Turn
    from bgclens.core.provenance import RunRecord
    from pathlib import Path

    _log.info("💬 [chat] message=%r run_ids=%s", req.message[:80], req.run_ids[:3])

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
    _log.info("  💬 reply: %d chars, mentions=%s", len(turn.content), [m.object_id for m in mentions])

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
