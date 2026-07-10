"""Analysis intent definition, validation, and method filtering."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from bgclens.model import Project


class Intent(str, Enum):
    # Existing (keep unchanged)
    enrichment = "enrichment"
    diversity = "diversity"
    ordination = "ordination"
    clustering = "clustering"
    comparison = "comparison"
    network_structure = "network_structure"
    # SQ taxonomy (Phase 1)
    sq1_inventory = "sq1_inventory"
    sq2_novelty = "sq2_novelty"
    sq3_prioritization = "sq3_prioritization"
    sq4_distribution = "sq4_distribution"
    sq5_diversity = "sq5_diversity"
    sq6_genomic_context = "sq6_genomic_context"
    sq7_association = "sq7_association"


SQ_LABELS: dict[str, str] = {
    "sq1_inventory":      "Inventory — what / how many BGCs?",
    "sq2_novelty":        "Novelty — known vs new?",
    "sq3_prioritization": "Prioritization — which to chase in the lab?",
    "sq4_distribution":   "Distribution — how spread across strains/taxa?",
    "sq5_diversity":      "Diversity / sampling — how diverse, is it saturated?",
    "sq6_genomic_context":"Genomic context — core vs accessory, resistance, HGT",
    "sq7_association":    "Association — do BGCs track phenotype/metadata?",
}

INTENT_REQUIREMENTS: dict[str, list[str]] = {
    "enrichment":        ["bgc_counts"],
    "diversity":         ["bgc_counts"],
    "ordination":        ["gcf_presence_absence"],
    "clustering":        ["gcf_presence_absence"],
    "comparison":        ["gcf_presence_absence"],
    "network_structure": ["gcf_network"],
    # SQ taxonomy (Phase 1)
    "sq1_inventory":      ["bgc_counts"],
    "sq2_novelty":        ["gcf_presence_absence"],
    "sq3_prioritization": ["gcf_presence_absence"],
    "sq4_distribution":   ["bgc_counts"],
    "sq5_diversity":      ["gcf_presence_absence"],
    "sq6_genomic_context":["gcf_network"],
    "sq7_association":    ["gcf_presence_absence"],
}

INTENT_PIPELINE_SOURCES: dict[str, str] = {
    "enrichment":        "antismash (BGC class counts per genome)",
    "diversity":         "antismash (BGC class counts per genome)",
    "ordination":        "bigscape (GCF presence/absence matrix)",
    "clustering":        "bigscape (GCF presence/absence matrix)",
    "comparison":        "bigscape (GCF presence/absence matrix)",
    "network_structure": "bigscape (GCF similarity network)",
    # SQ taxonomy (Phase 1)
    "sq1_inventory":      "antismash (BGC class counts per genome)",
    "sq2_novelty":        "bigscape (GCF family novelty via MIBiG distance)",
    "sq3_prioritization": "bigscape (GCF presence/absence matrix)",
    "sq4_distribution":   "antismash (BGC class counts per genome)",
    "sq5_diversity":      "bigscape (GCF presence/absence matrix)",
    "sq6_genomic_context":"bigscape (GCF similarity network)",
    "sq7_association":    "bigscape (GCF presence/absence matrix)",
}


@dataclass
class AnalysisRequest:
    topic: str
    intent: Intent
    method_hint: str | None = None   # optional pre-selected method_id


@dataclass
class IntentValidation:
    valid: bool
    intent: str
    missing_data: list[str] = field(default_factory=list)
    suggestion: str = ""


def validate_intent(project: Project, intent: Intent | str) -> IntentValidation:
    """Check whether the project has the data required for this intent."""
    intent_str = intent.value if isinstance(intent, Intent) else str(intent)
    required = INTENT_REQUIREMENTS.get(intent_str, [])
    missing = []

    data_map = {
        "gcf_presence_absence": project.gcf_presence_absence,
        "bgc_counts": project.bgc_counts,
        "gcf_network": project.gcf_network,
        "taxonomy": project.taxonomy,
        "quality": project.quality,
    }

    for field_name in required:
        if data_map.get(field_name) is None:
            missing.append(field_name)

    if missing:
        source = INTENT_PIPELINE_SOURCES.get(intent_str, "the appropriate BGCFlow pipeline")
        suggestion = (
            f"The '{intent_str}' intent requires {', '.join(missing)} which was not found in the project. "
            f"Please run {source} with BGCFlow first, then re-ingest the project."
        )
        return IntentValidation(valid=False, intent=intent_str, missing_data=missing, suggestion=suggestion)

    return IntentValidation(valid=True, intent=intent_str)


def filter_methods_for_intent(intent: Intent | str, project: Project) -> list[dict]:
    """Return catalog methods valid for this intent and the project's available data."""
    from bgclens.catalog.registry import methods_for_intent

    intent_str = intent.value if isinstance(intent, Intent) else str(intent)
    candidates = methods_for_intent(intent_str)

    # Filter by available data
    available = []
    for method in candidates:
        requires = method.get("requires", {})
        ok = True
        if "presence_absence" in requires and project.gcf_presence_absence is None:
            ok = False
        if "counts" in requires and project.bgc_counts is None:
            ok = False
        if "network" in requires and project.gcf_network is None:
            ok = False
        if ok:
            available.append(method)

    return available
