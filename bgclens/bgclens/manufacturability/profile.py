"""Manufacturability weight profile: reorder recommendations by tractability signal."""
from __future__ import annotations
from dataclasses import dataclass
from bgclens.manufacturability.features import TierAFeatures


@dataclass
class ManufacturabilityProfile:
    tractability_score: float
    n_bgcs: int
    top_class: str | None
    notes: list[str]


# Methods that are more useful for high-tractability collections (RiPPs, Terpenes)
# vs. low-tractability (PKS-I heavy): ordination is universal, enrichment biases
# toward known classes which helps for tractable sets.
_HIGH_TRACTABILITY_BOOST: set[str] = {"fisher_enrichment", "diversity"}
_LOW_TRACTABILITY_BOOST: set[str] = {"pcoa", "pca", "clustering"}


def compute_profile(features: TierAFeatures) -> ManufacturabilityProfile:
    top_class = None
    if features.bgc_class_counts:
        top_class = max(features.bgc_class_counts, key=features.bgc_class_counts.get)
    return ManufacturabilityProfile(
        tractability_score=features.tractability_score,
        n_bgcs=features.n_bgcs,
        top_class=top_class,
        notes=features.notes,
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
