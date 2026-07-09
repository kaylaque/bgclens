"""PERMANOVA using scikit-bio."""
from typing import Any
import numpy as np
from bgclens.model import PresenceAbsenceMatrix, MetadataTable


def run(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    try:
        from skbio.stats.distance import permanova, DistanceMatrix
        from scipy.spatial.distance import pdist, squareform
    except ImportError:
        return {
            "error": "scikit-bio is required for PERMANOVA. Install with: pip install 'bgclens[bio]'"
        }

    pa: PresenceAbsenceMatrix = inputs["presence_absence"]
    metadata: MetadataTable | None = inputs.get("metadata")
    grouping_col: str = inputs.get("grouping_col") or params.get("grouping_col", "")
    metric: str = params.get("metric", "braycurtis")
    permutations: int = int(params.get("permutations", 999))

    mat = pa.to_numpy().T.astype(float)
    genome_ids = list(pa.cols)

    dist_arr = squareform(pdist(mat, metric=metric))
    dm = DistanceMatrix(dist_arr, ids=genome_ids)

    # Build grouping series
    if metadata and grouping_col:
        id_to_group = {row["genome_id"]: row.get(grouping_col) for row in metadata.rows}
        grouping = [str(id_to_group.get(gid, "unknown")) for gid in genome_ids]
    else:
        grouping = [
            "group_a" if i < len(genome_ids) // 2 else "group_b"
            for i in range(len(genome_ids))
        ]

    import pandas as pd

    result = permanova(dm, pd.Series(grouping, index=genome_ids), permutations=permutations)

    return {
        "method": "permanova",
        "metric": metric,
        "permutations": permutations,
        "grouping_col": grouping_col,
        "test_statistic": float(result["test statistic"]),
        "pvalue": float(result["p-value"]),
        "n_genomes": len(genome_ids),
        "groups": sorted(set(grouping)),
    }


def check_assumptions(inputs: dict[str, Any], params: dict[str, Any]) -> list[str]:
    warnings = []
    pa: PresenceAbsenceMatrix | None = inputs.get("presence_absence")
    if pa is None:
        warnings.append("No PresenceAbsenceMatrix provided.")
        return warnings
    n = len(pa.cols)
    if n < 6:
        warnings.append(f"Only {n} genomes — PERMANOVA needs at least 3 per group.")
    metadata: MetadataTable | None = inputs.get("metadata")
    grouping_col = inputs.get("grouping_col") or params.get("grouping_col")
    if metadata and grouping_col:
        vals = [row.get(grouping_col) for row in metadata.rows]
        from collections import Counter

        counts = Counter(v for v in vals if v is not None)
        if any(c < 3 for c in counts.values()):
            warnings.append("Some groups have fewer than 3 genomes — PERMANOVA unreliable.")
        if len(set(counts.values())) > 1:
            sizes = dict(counts)
            warnings.append(
                f"Unbalanced groups {sizes} — PERMANOVA is sensitive to heteroscedasticity."
            )
    return warnings


def cost(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    pa: PresenceAbsenceMatrix | None = inputs.get("presence_absence")
    if pa is None:
        return {"class": "Safe", "reason": "No data", "estimated_mb": 0.0}
    n = len(pa.cols)
    perms = int((inputs.get("params") or params or {}).get("permutations", 999))
    mb = (n * n * 8) / 1e6 * (1 + perms / 100)
    cls = "Safe" if n <= 100 else "Heavy" if n <= 400 else "Likely-to-fail"
    return {
        "class": cls,
        "reason": f"N={n} genomes × {perms} permutations → {mb:.0f} MB",
        "estimated_mb": mb,
    }
