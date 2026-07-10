"""Core engine API — the only thing CLI and web surfaces import for analysis."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bgclens.adapters.detect import detect_project
from bgclens.adapters import csv_adapter, duckdb_adapter
from bgclens.model import Project
from bgclens.core.intent import (
    AnalysisRequest, Intent, IntentValidation,
    validate_intent, filter_methods_for_intent,
)

logger = logging.getLogger(__name__)


class MissingRequirementError(ValueError):
    """Raised when a method requires data that is absent from the project."""


def open_project(path: Path | str) -> Project:
    """Ingest a finished BGCFlow project directory and return a loaded Project.

    Uses DuckDB when present; falls back to CSV/TSV files.

    Raises:
        ValueError: if the path is not a valid BGCFlow project.
    """
    path = Path(path)
    manifest = detect_project(path)

    # Prefer DuckDB when available
    gcf_pa = None
    taxonomy = None
    if manifest.duckdb_path:
        gcf_pa = duckdb_adapter.load_gcf_presence_absence(manifest.duckdb_path)
        taxonomy = duckdb_adapter.load_taxonomy(manifest.duckdb_path)

    # CSV fallback
    if gcf_pa is None:
        gcf_pa = csv_adapter.load_gcf_presence_absence(path)
    if taxonomy is None:
        taxonomy = csv_adapter.load_taxonomy(path)

    bgc_counts = csv_adapter.load_bgc_counts(path)
    quality = csv_adapter.load_quality(path)
    metadata = csv_adapter.load_metadata(path)

    return Project(
        manifest=manifest,
        gcf_presence_absence=gcf_pa,
        bgc_counts=bgc_counts,
        taxonomy=taxonomy,
        quality=quality,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Method recommendation engine
# ---------------------------------------------------------------------------

@dataclass
class MethodRecommendation:
    method_id: str
    method_name: str
    intent: str
    cost_class: str           # "Safe" | "Heavy" | "Likely-to-fail"
    cost_reason: str
    assumption_warnings: list[str] = field(default_factory=list)
    literature_support: str = "unknown"    # "strong"|"moderate"|"weak"|"none"|"unknown"
    literature_citations: list[dict] = field(default_factory=list)
    is_recommended: bool = False
    alternatives: list[dict] = field(default_factory=list)


def recommend(
    project: "Project",
    request: AnalysisRequest,
    use_literature: bool = True,
) -> tuple[IntentValidation, list[MethodRecommendation]]:
    """
    Recommend methods for the given intent + topic.
    Returns (validation, recommendations).
    If validation.valid is False, recommendations is empty.
    """
    validation = validate_intent(project, request.intent)
    if not validation.valid:
        return validation, []

    candidates = filter_methods_for_intent(request.intent, project)
    if not candidates:
        return validation, []

    # Apply method_hint filter when specified
    if request.method_hint:
        hinted = [m for m in candidates if m["id"] == request.method_hint]
        if hinted:
            candidates = hinted

    try:
        # Cost assessment for each candidate
        recommendations: list[MethodRecommendation] = []
        for method in candidates:
            method_id = method["id"]

            # Assumption checks
            try:
                from bgclens.catalog.registry import get_impl
                _, check_fn, _ = get_impl(method_id)
                method_inputs = _build_inputs(project, method)
                warnings = check_fn(method_inputs, {})
            except MissingRequirementError:
                raise
            except (KeyError, AttributeError, ImportError) as e:
                logger.warning("assumption check skipped for %s: %s", method_id, e)
                warnings = []

            # Cost assessment
            try:
                from bgclens.compute.advisor import assess
                method_inputs = _build_inputs(project, method)
                assessment = assess(method_id, method_inputs, {})
                cost_class = assessment.cost_class
                cost_reason = assessment.reason
                alts = [{"method_id": a.method_id, "trade_off": a.trade_off} for a in assessment.alternatives]
            except MissingRequirementError:
                raise
            except (ImportError, KeyError, ValueError) as e:
                logger.warning("cost estimation unavailable for %s: %s", method_id, e)
                cost_class = "Safe"
                cost_reason = f"Cost estimation unavailable: {e}"
                alts = []

            recommendations.append(MethodRecommendation(
                method_id=method_id,
                method_name=method.get("name", method_id),
                intent=request.intent.value if isinstance(request.intent, Intent) else str(request.intent),
                cost_class=cost_class,
                cost_reason=cost_reason,
                assumption_warnings=warnings,
                alternatives=alts,
            ))

        # Literature ranking (optional, graceful fallback)
        if use_literature:
            try:
                from bgclens.literature.openalex import OpenAlexProvider
                from bgclens.literature.ranker import rank_methods
                method_names = {r.method_id: r.method_name for r in recommendations}
                ranking = rank_methods(
                    method_ids=[r.method_id for r in recommendations],
                    method_display_names=method_names,
                    topic=request.topic,
                    provider=OpenAlexProvider(),
                )
                rank_map = {s.method_id: s for s in ranking.method_rankings}
                for rec in recommendations:
                    support = rank_map.get(rec.method_id)
                    if support:
                        rec.literature_support = support.support_level
                        rec.literature_citations = [
                            {"title": c.title, "year": c.year, "doi": c.doi}
                            for c in support.citations
                        ]
            except Exception as e:
                logger.warning("literature ranking skipped: %s", e)

    except MissingRequirementError as e:
        intent_str = request.intent.value if isinstance(request.intent, Intent) else str(request.intent)
        return IntentValidation(valid=False, intent=intent_str, missing_data=[], suggestion=str(e)), []

    # Mark top recommended method (Safe + strongest literature support or first Safe)
    safe_recs = [r for r in recommendations if r.cost_class == "Safe"]
    if safe_recs:
        # Prefer literature-supported safe methods
        order = {"strong": 0, "moderate": 1, "weak": 2, "none": 3, "unknown": 4}
        safe_recs.sort(key=lambda r: order.get(r.literature_support, 4))
        safe_recs[0].is_recommended = True

    return validation, recommendations


def run(project: "Project", method_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a method and return the structured result with provenance."""
    from bgclens.catalog.registry import get_impl, get_method
    from bgclens.core.provenance import RunRecord, hash_project

    params = params or {}
    method_entry = get_method(method_id)
    run_fn, check_fn, _ = get_impl(method_id)

    inputs = _build_inputs(project, method_entry)
    warnings = check_fn(inputs, params)
    result = run_fn(inputs, params)
    result["_assumption_warnings"] = warnings
    result["_method_id"] = method_id
    result["_provenance"] = {
        "inputs_hash": hash_project(project.manifest.source_path),
        "method_id": method_id,
        "params": params,
    }
    return result


def _build_inputs(project: "Project", method_entry: dict) -> dict:
    """Build the inputs dict for a method from the loaded project.

    Raises:
        MissingRequirementError: when a required dataset is absent from the project.
    """
    requires = method_entry.get("requires", {}) if method_entry else {}
    inputs: dict = {}

    if "presence_absence" in requires:
        if project.gcf_presence_absence is None:
            raise MissingRequirementError(
                "presence_absence matrix required but not found. Run BiG-SCAPE with BGCFlow first."
            )
        inputs["presence_absence"] = project.gcf_presence_absence
    if "counts" in requires:
        if project.bgc_counts is None:
            raise MissingRequirementError(
                "bgc_counts table required but not found. Run antiSMASH with BGCFlow first."
            )
        inputs["counts"] = project.bgc_counts
    if "network" in requires:
        if project.gcf_network is None:
            raise MissingRequirementError(
                "gcf_network required but not found. Run BiG-SCAPE with BGCFlow first."
            )
        inputs["network"] = project.gcf_network
    if project.metadata:
        inputs["metadata"] = project.metadata

    return inputs
