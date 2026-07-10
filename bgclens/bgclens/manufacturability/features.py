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


def compute_features(project: Project) -> TierAFeatures:
    """Extract Tier-A features from a loaded Project. Never raises."""
    features = TierAFeatures()

    try:
        if project.bgc_counts is not None:
            df = project.bgc_counts.data
            if df is None:
                features.notes.append("bgc_counts.data is None")
            else:
                features.n_bgcs = int(df.values.sum()) if hasattr(df, "values") else 0
                col_sums = df.sum(axis=0) if hasattr(df, "sum") else {}
                features.bgc_class_counts = {
                    col: int(col_sums[col]) for col in df.columns
                } if hasattr(df, "columns") else {}
    except Exception as exc:
        features.notes.append(f"bgc_counts extraction failed: {exc}")

    try:
        if project.quality is not None:
            df = project.quality.data
            if hasattr(df, "columns"):
                gc_cols = [c for c in df.columns if "gc" in c.lower()]
                if gc_cols:
                    features.gc_content_mean = float(df[gc_cols[0]].mean())
    except Exception as exc:
        features.notes.append(f"gc_content extraction failed: {exc}")

    total_bgcs = sum(features.bgc_class_counts.values())
    if total_bgcs > 0:
        weighted = sum(
            count * _CLASS_TRACTABILITY.get(cls, _DEFAULT_TRACTABILITY)
            for cls, count in features.bgc_class_counts.items()
        )
        features.tractability_score = weighted / total_bgcs

    return features
