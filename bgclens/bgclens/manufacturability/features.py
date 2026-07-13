"""Tier-A deterministic manufacturability features from BGCFlow outputs."""
from __future__ import annotations
from dataclasses import dataclass, field
from bgclens.model import Project


@dataclass
class TierAFeatures:
    n_bgcs: int = 0
    mean_cluster_size_kb: float = 0.0
    gc_content_mean: float | None = None
    bgc_class_counts: dict[str, int] = field(default_factory=dict)
    tractability_score: float = 0.0
    notes: list[str] = field(default_factory=list)


# BGC classes ordered by heterologous expression tractability
# (heuristic based on literature; PKS-I hardest, RiPPs easiest)
_CLASS_TRACTABILITY: dict[str, float] = {
    "RiPP": 0.9,
    "Terpene": 0.85,
    "NRP": 0.7,
    "PKS-I": 0.4,
    "PKS-II": 0.45,
    "PKS-other": 0.5,
    "NRPS": 0.65,
    "Hybrid": 0.55,
    "Other": 0.6,
}
_DEFAULT_TRACTABILITY = 0.5


# Substring markers that map a raw antiSMASH product label to a coarse BGC class.
# Real labels look like "lanthipeptide-class-iii", "RiPP-like", "terpene-precursor",
# "T1PKS", "NRPS", "NRPS-like", "transAT-PKS", so matching is case-insensitive and
# substring-based rather than exact.
_RIPP_MARKERS = (
    "ripp",
    "lanthipeptide",
    "lantipeptide",
    "lassopeptide",
    "lasso",
    "thiopeptide",
    "sactipeptide",
    "bacteriocin",
    "microcin",
    "graspetide",
    "linaridin",
    "cyanobactin",
    "lap",
    "head_to_tail",
    "proteusin",
    "glycocin",
    "lanthidin",
)


def _normalize_class(label: str) -> str:
    """Map a raw antiSMASH product label to a coarse tractability class.

    Case-insensitive, substring-based, robust to hyphenated/suffixed labels.
    """
    lab = str(label).lower()
    if "hybrid" in lab or ("nrps" in lab and "pks" in lab):
        return "Hybrid"
    if any(marker in lab for marker in _RIPP_MARKERS):
        return "RiPP"
    if "terpene" in lab:
        return "Terpene"
    if "t1pks" in lab or "type i pks" in lab or "transat" in lab or "pks-i" in lab:
        return "PKS-I"
    if "t2pks" in lab or "pks-ii" in lab:
        return "PKS-II"
    if "t3pks" in lab or "pks-iii" in lab or "pks-other" in lab or "pks" in lab:
        return "PKS-other"
    if "nrps" in lab or "nonribosomal" in lab or "nrp" in lab:
        return "NRPS"
    return "Other"


def compute_features(project: Project) -> TierAFeatures:
    """Extract Tier-A features from a loaded Project. Never raises."""
    features = TierAFeatures()

    try:
        table = project.bgc_counts
        if table is None:
            features.notes.append("no bgc_counts table available")
        elif not table.features or not table.counts:
            features.notes.append("bgc_counts table is empty")
        else:
            # counts shape: len(genome_ids) x len(features). Sum over genomes
            # (axis=0) to get a per-class total keyed by the raw feature name.
            matrix = table.to_numpy()
            totals = matrix.sum(axis=0)
            features.bgc_class_counts = {
                name: int(totals[j]) for j, name in enumerate(table.features)
            }
    except Exception as exc:  # never raise
        features.notes.append(f"bgc_counts extraction failed: {exc}")

    # GC content is not derivable: QualityTable exposes completeness /
    # contamination / strain_heterogeneity only — no GC column.
    features.gc_content_mean = None
    features.notes.append(
        "GC content unavailable: QualityTable exposes no GC field, so GC-based "
        "codon/assembly compatibility cannot be assessed from the loaded tables."
    )

    total_bgcs = sum(features.bgc_class_counts.values())
    features.n_bgcs = total_bgcs
    if total_bgcs > 0:
        weighted = sum(
            count * _CLASS_TRACTABILITY.get(_normalize_class(name), _DEFAULT_TRACTABILITY)
            for name, count in features.bgc_class_counts.items()
        )
        features.tractability_score = weighted / total_bgcs

    return features
