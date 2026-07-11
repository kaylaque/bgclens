"""Manufacturability weight profile: reorder recommendations by tractability signal."""
from __future__ import annotations
from dataclasses import dataclass, field
from bgclens.manufacturability.features import TierAFeatures, _normalize_class


@dataclass
class ManufacturabilityProfile:
    tractability_score: float
    n_bgcs: int
    top_class: str | None
    notes: list[str] = field(default_factory=list)
    chassis_hint: dict | None = None
    blockers: list[str] = field(default_factory=list)


# Catalog method IDs (from bgclens/catalog/entries/*.yaml):
# alpha_diversity, hierarchical_clustering, fisher_enrichment, pca, pcoa,
# louvain_community, permanova. High-tractability collections (RiPPs, Terpenes)
# benefit from enrichment/diversity views; low-tractability (PKS-I heavy) sets
# benefit from ordination + clustering to explore structure.
_HIGH_TRACTABILITY_BOOST: set[str] = {"fisher_enrichment", "alpha_diversity"}
_LOW_TRACTABILITY_BOOST: set[str] = {"pcoa", "pca", "hierarchical_clustering"}


# Fixed chassis panel for the honest MVP heuristic.
_CHASSIS_ECOLI = "E. coli"
_CHASSIS_ALBUS = "S. albus J1074"
_CHASSIS_YEAST = "S. cerevisiae"
_CHASSIS_PUTIDA = "P. putida"


def chassis_hint(top_class: str | None, taxonomy=None) -> dict | None:
    """Suggest an expression chassis from a fixed panel via a simple heuristic.

    Panel: {E. coli, S. albus J1074, S. cerevisiae, P. putida}.
    RiPP/small -> E. coli; terpene -> S. cerevisiae; PKS/NRPS-heavy -> S. albus;
    default -> E. coli. Returns None when no dominant class is available.
    """
    if not top_class:
        return None

    cls = _normalize_class(top_class)

    if cls == "Terpene":
        return {
            "organism": _CHASSIS_YEAST,
            "reason": (
                "Terpene pathways rely on eukaryotic isoprenoid precursors and P450 "
                "processing that a yeast chassis supplies natively."
            ),
        }
    if cls == "RiPP":
        return {
            "organism": _CHASSIS_ECOLI,
            "reason": (
                "RiPPs are small ribosomally-synthesised peptides that express and fold "
                "well in E. coli without a large PPTase-dependent assembly line."
            ),
        }
    if cls in ("PKS-I", "PKS-II", "PKS-other", "NRPS", "NRP", "Hybrid"):
        return {
            "organism": _CHASSIS_ALBUS,
            "reason": (
                "PKS/NRPS megasynthases need actinomycete precursor pools, PPTase "
                "activity and GC-rich codon usage best matched by S. albus J1074."
            ),
        }
    return {
        "organism": _CHASSIS_ECOLI,
        "reason": "Default general-purpose chassis for an unclassified dominant BGC class.",
    }


def blocker_flags(bgc_class_counts: dict[str, int]) -> list[str]:
    """Honest manufacturability blockers implied by the BGC class composition."""
    flags: list[str] = []
    classes = {_normalize_class(name) for name in bgc_class_counts}

    if any(c in ("NRPS", "NRP", "PKS-I", "PKS-II", "PKS-other", "Hybrid") for c in classes):
        flags.append("needs PPTase for NRPS/PKS")
    if "PKS-I" in classes:
        flags.append("megasynthase (large PKS-I) — low assembly tractability")

    # GC content is never derivable from the available tables, so GC-driven
    # codon/assembly risk cannot be ruled out — a standing honest blocker.
    flags.append("high-GC unknown (GC not derivable from available tables)")
    return flags


def compute_profile(features: TierAFeatures, taxonomy=None) -> ManufacturabilityProfile:
    top_class = None
    if features.bgc_class_counts:
        top_class = max(features.bgc_class_counts, key=features.bgc_class_counts.get)
    return ManufacturabilityProfile(
        tractability_score=features.tractability_score,
        n_bgcs=features.n_bgcs,
        top_class=top_class,
        notes=features.notes,
        chassis_hint=chassis_hint(top_class, taxonomy),
        blockers=blocker_flags(features.bgc_class_counts),
    )


def reorder_for_manufacturability(
    recommendations: list,
    profile: ManufacturabilityProfile,
) -> list:
    """Return recommendations reordered by manufacturability objective.

    High tractability (>=0.7): boost enrichment + diversity first.
    Low tractability (<0.5): boost ordination + clustering first (explore diversity).
    Middle: return unchanged order.
    """
    if not recommendations:
        return recommendations

    score = profile.tractability_score

    if score >= 0.7:
        boost = _HIGH_TRACTABILITY_BOOST
    elif score < 0.5:
        boost = _LOW_TRACTABILITY_BOOST
    else:
        return recommendations

    boosted = [r for r in recommendations if r.method_id in boost]
    rest = [r for r in recommendations if r.method_id not in boost]
    return boosted + rest
