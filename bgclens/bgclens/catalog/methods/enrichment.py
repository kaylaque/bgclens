"""Fisher's exact test for BGC class enrichment between two genome groups."""
from typing import Any
import numpy as np
from scipy.stats import fisher_exact
from bgclens.model import FeatureCountTable, MetadataTable


def _split_groups(
    counts: FeatureCountTable, metadata: MetadataTable | None, grouping_col: str
) -> tuple[np.ndarray, np.ndarray] | None:
    """Return (group_a_indices, group_b_indices) or None if can't split."""
    if metadata is None:
        return None
    group_vals = [row.get(grouping_col) for row in metadata.rows]
    unique = sorted({v for v in group_vals if v is not None})
    if len(unique) < 2:
        return None
    a_idx = [i for i, v in enumerate(group_vals) if v == unique[0]]
    b_idx = [i for i, v in enumerate(group_vals) if v == unique[1]]
    return np.array(a_idx), np.array(b_idx)


def run(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    counts: FeatureCountTable = inputs["counts"]
    metadata: MetadataTable | None = inputs.get("metadata")
    grouping_col: str = params.get("grouping_col") or (
        metadata.columns[1] if metadata and len(metadata.columns) > 1 else "group"
    )
    correction: str = params.get("correction", "bh")
    alpha: float = float(params.get("alpha", 0.05))

    mat = counts.to_numpy()  # shape: genomes × features
    split = _split_groups(counts, metadata, grouping_col)

    if split is None:
        return {
            "error": f"Cannot find two groups in metadata column '{grouping_col}'",
            "features": counts.features,
            "pvalues_raw": [],
            "pvalues_adj": [],
            "odds_ratios": [],
        }

    a_idx, b_idx = split
    n_features = mat.shape[1]
    pvalues_raw = []
    odds_ratios = []

    for j in range(n_features):
        col = mat[:, j]
        a_present = int((col[a_idx] > 0).sum())
        a_absent = int((col[a_idx] == 0).sum())
        b_present = int((col[b_idx] > 0).sum())
        b_absent = int((col[b_idx] == 0).sum())
        table = [[a_present, a_absent], [b_present, b_absent]]
        or_, p = fisher_exact(table, alternative="two-sided")
        pvalues_raw.append(float(p))
        odds_ratios.append(float(or_) if np.isfinite(or_) else None)

    # Multiple testing correction
    pvalues_adj = _correct(pvalues_raw, correction, alpha)

    significant = [
        counts.features[j]
        for j in range(n_features)
        if pvalues_adj[j] is not None and pvalues_adj[j] <= alpha
    ]

    return {
        "test": "fisher_exact",
        "grouping_col": grouping_col,
        "groups": [str(g) for g in sorted({
            row.get(grouping_col) for row in (metadata.rows if metadata else [])
            if row.get(grouping_col) is not None
        })],
        "n_group_a": int(len(a_idx)),
        "n_group_b": int(len(b_idx)),
        "features": counts.features,
        "pvalues_raw": pvalues_raw,
        "pvalues_adj": pvalues_adj,
        "odds_ratios": odds_ratios,
        "correction": correction,
        "alpha": alpha,
        "significant_features": significant,
        "n_significant": len(significant),
    }


def _correct(pvalues: list[float], method: str, alpha: float) -> list[float | None]:
    if method == "none":
        return pvalues
    try:
        from statsmodels.stats.multitest import multipletests
        reject, pvals_corrected, _, _ = multipletests(
            pvalues, alpha=alpha, method="fdr_bh" if method == "bh" else method
        )
        return [float(p) for p in pvals_corrected]
    except Exception:
        return pvalues  # fallback if statsmodels unavailable


def check_assumptions(inputs: dict[str, Any], params: dict[str, Any]) -> list[str]:
    warnings = []
    counts: FeatureCountTable = inputs.get("counts")
    if counts is None:
        warnings.append("No FeatureCountTable provided.")
        return warnings
    n = len(counts.genome_ids)
    if n < 4:
        warnings.append(f"Only {n} genomes — Fisher's test is unreliable with very small groups.")
    metadata: MetadataTable | None = inputs.get("metadata")
    grouping_col = params.get("grouping_col")
    if metadata and grouping_col:
        vals = [row.get(grouping_col) for row in metadata.rows if row.get(grouping_col)]
        unique = set(vals)
        if len(unique) < 2:
            warnings.append(f"Column '{grouping_col}' has only one group value — cannot compare.")
    return warnings


def cost(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    counts: FeatureCountTable | None = inputs.get("counts")
    if counts is None:
        return {"class": "Safe", "reason": "No data yet", "estimated_mb": 0.0}
    n = len(counts.genome_ids)
    f = len(counts.features)
    mb = (n * f * 8) / 1e6
    cls = "Safe" if mb < 100 else "Heavy" if mb < 1000 else "Likely-to-fail"
    return {
        "class": cls,
        "reason": f"{n} genomes × {f} features → {mb:.1f} MB",
        "estimated_mb": mb,
    }
