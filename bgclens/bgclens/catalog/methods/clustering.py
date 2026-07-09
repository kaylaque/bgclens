"""Hierarchical clustering of genomes by GCF presence/absence."""
from typing import Any
import numpy as np
from bgclens.model import PresenceAbsenceMatrix


def run(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    from scipy.spatial.distance import pdist, squareform
    from scipy.cluster.hierarchy import linkage, fcluster, to_tree

    pa: PresenceAbsenceMatrix = inputs["presence_absence"]
    metric: str = params.get("metric", "braycurtis")
    link_method: str = params.get("linkage", "ward")
    n_clusters = params.get("n_clusters")

    mat = pa.to_numpy().T.astype(float)  # genomes × GCFs
    genome_ids = list(pa.cols)

    if link_method == "ward" and metric != "euclidean":
        metric = "euclidean"  # Ward requires euclidean

    dists = pdist(mat, metric=metric)
    Z = linkage(dists, method=link_method)

    cluster_labels: list[int] | None = None
    if n_clusters is not None:
        labels = fcluster(Z, int(n_clusters), criterion="maxclust")
        cluster_labels = labels.tolist()

    return {
        "method": "hierarchical_clustering",
        "metric": metric,
        "linkage": link_method,
        "genome_ids": genome_ids,
        "linkage_matrix": Z.tolist(),
        "cluster_labels": cluster_labels,
        "n_clusters_requested": n_clusters,
        "n_genomes": len(genome_ids),
    }


def check_assumptions(inputs: dict[str, Any], params: dict[str, Any]) -> list[str]:
    warnings = []
    pa: PresenceAbsenceMatrix | None = inputs.get("presence_absence")
    if pa is None:
        warnings.append("No PresenceAbsenceMatrix provided.")
        return warnings
    if len(pa.cols) < 4:
        warnings.append(
            f"Only {len(pa.cols)} genomes — clustering is trivial with very few samples."
        )
    return warnings


def cost(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    pa: PresenceAbsenceMatrix | None = inputs.get("presence_absence")
    if pa is None:
        return {"class": "Safe", "reason": "No data", "estimated_mb": 0.0}
    n = len(pa.cols)
    mb = (n * n * 8) / 1e6
    cls = "Safe" if n <= 500 else "Heavy" if n <= 2000 else "Likely-to-fail"
    return {
        "class": cls,
        "reason": f"N={n} pairwise distances ({mb:.0f} MB)",
        "estimated_mb": mb,
    }
