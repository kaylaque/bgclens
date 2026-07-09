"""PCoA and PCA ordination methods."""
from typing import Any
import numpy as np
from bgclens.model import PresenceAbsenceMatrix, FeatureCountTable


def run_pcoa(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Principal Coordinates Analysis using scipy distance + eigendecomposition."""
    from scipy.spatial.distance import pdist, squareform

    pa: PresenceAbsenceMatrix = inputs["presence_absence"]
    metric: str = params.get("metric", "braycurtis")
    n_comp: int = int(params.get("n_components", 3))
    subsample_n = params.get("subsample_n")

    mat = pa.to_numpy().T.astype(float)  # shape: genomes × GCFs
    genome_ids = list(pa.cols)

    if subsample_n and len(genome_ids) > subsample_n:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(genome_ids), size=subsample_n, replace=False)
        mat = mat[idx]
        genome_ids = [genome_ids[i] for i in idx]
        subsampled = True
    else:
        subsampled = False

    dist = squareform(pdist(mat, metric=metric))
    n = dist.shape[0]

    # Classical MDS / PCoA
    H = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * H @ (dist ** 2) @ H
    eigenvalues, eigenvectors = np.linalg.eigh(B)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]

    pos_mask = eigenvalues > 1e-10
    k = min(n_comp, pos_mask.sum())
    coords = eigenvectors[:, :k] * np.sqrt(np.maximum(eigenvalues[:k], 0))

    total_var = eigenvalues[pos_mask].sum()
    explained = (eigenvalues[:k] / total_var * 100).tolist() if total_var > 0 else [0.0] * k

    return {
        "method": "pcoa",
        "metric": metric,
        "genome_ids": genome_ids,
        "coordinates": coords.tolist(),
        "n_components": k,
        "explained_variance_pct": explained,
        "subsampled": subsampled,
        "n_genomes": len(genome_ids),
        "n_gcfs": mat.shape[1],
    }


def run_pca(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """PCA on FeatureCountTable."""
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    counts: FeatureCountTable = inputs["counts"]
    n_comp: int = min(
        int(params.get("n_components", 3)),
        len(counts.genome_ids),
        len(counts.features),
    )
    scale: bool = bool(params.get("scale", True))

    mat = counts.to_numpy().astype(float)
    if scale:
        mat = StandardScaler().fit_transform(mat)

    pca = PCA(n_components=n_comp, random_state=42)
    coords = pca.fit_transform(mat)

    return {
        "method": "pca",
        "genome_ids": counts.genome_ids,
        "coordinates": coords.tolist(),
        "n_components": n_comp,
        "explained_variance_pct": (pca.explained_variance_ratio_ * 100).tolist(),
        "feature_loadings": pca.components_.tolist(),
        "features": counts.features,
        "n_genomes": len(counts.genome_ids),
    }


def check_assumptions(inputs: dict[str, Any], params: dict[str, Any]) -> list[str]:
    warnings = []
    pa = inputs.get("presence_absence") or inputs.get("counts")
    if pa is None:
        warnings.append("No input data provided.")
        return warnings
    n = len(getattr(pa, "cols", getattr(pa, "genome_ids", [])))
    if n < 5:
        warnings.append(f"Only {n} genomes — ordination with very few samples is unreliable.")
    return warnings


def pcoa_cost(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    pa: PresenceAbsenceMatrix | None = inputs.get("presence_absence")
    if pa is None:
        return {"class": "Safe", "reason": "No data", "estimated_mb": 0.0}
    n = len(pa.cols)
    mb = (n * n * 8) / 1e6  # distance matrix
    cls = "Safe" if n <= 200 else "Heavy" if n <= 800 else "Likely-to-fail"
    return {
        "class": cls,
        "reason": f"N={n} genomes → {n}×{n} distance matrix ({mb:.0f} MB)",
        "estimated_mb": mb,
    }


def pca_cost(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    counts: FeatureCountTable | None = inputs.get("counts")
    if counts is None:
        return {"class": "Safe", "reason": "No data", "estimated_mb": 0.0}
    mb = (len(counts.genome_ids) * len(counts.features) * 8) / 1e6
    cls = "Safe" if mb < 200 else "Heavy"
    return {"class": cls, "reason": f"matrix {mb:.1f} MB", "estimated_mb": mb}


# The run() and cost() shims for registry compatibility
run = run_pcoa
cost = pcoa_cost
