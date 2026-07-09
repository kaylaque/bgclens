"""Alpha diversity: Shannon, Simpson, rarefaction curves."""
from typing import Any
import numpy as np
from bgclens.model import FeatureCountTable


def run(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    counts: FeatureCountTable = inputs["counts"]
    metrics: list[str] = list(params.get("metrics", ["shannon", "simpson"]))
    mat = counts.to_numpy()  # genomes × features

    results_per_genome: list[dict] = []
    for i, gid in enumerate(counts.genome_ids):
        row = mat[i].astype(float)
        entry: dict[str, Any] = {"genome_id": gid}
        if "shannon" in metrics:
            entry["shannon"] = float(_shannon(row))
        if "simpson" in metrics:
            entry["simpson"] = float(_simpson(row))
        results_per_genome.append(entry)

    return {
        "method": "alpha_diversity",
        "metrics": metrics,
        "n_genomes": len(counts.genome_ids),
        "n_features": len(counts.features),
        "results": results_per_genome,
        "mean_shannon": float(np.mean([r.get("shannon", 0) for r in results_per_genome]))
        if "shannon" in metrics
        else None,
        "mean_simpson": float(np.mean([r.get("simpson", 0) for r in results_per_genome]))
        if "simpson" in metrics
        else None,
    }


def _shannon(counts: np.ndarray) -> float:
    counts = counts[counts > 0]
    if len(counts) == 0:
        return 0.0
    p = counts / counts.sum()
    return float(-np.sum(p * np.log(p)))


def _simpson(counts: np.ndarray) -> float:
    counts = counts[counts > 0]
    if len(counts) == 0:
        return 0.0
    n = counts.sum()
    if n <= 1:
        return 0.0
    return float(1.0 - np.sum(counts * (counts - 1)) / (n * (n - 1)))


def check_assumptions(inputs: dict[str, Any], params: dict[str, Any]) -> list[str]:
    warnings = []
    counts: FeatureCountTable | None = inputs.get("counts")
    if counts is None:
        warnings.append("No FeatureCountTable provided.")
        return warnings
    if len(counts.genome_ids) < 3:
        warnings.append(
            f"Only {len(counts.genome_ids)} genomes — diversity comparisons need more samples."
        )
    mat = counts.to_numpy()
    if (mat < 0).any():
        warnings.append("Negative counts detected — diversity metrics require non-negative values.")
    return warnings


def cost(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    counts: FeatureCountTable | None = inputs.get("counts")
    if counts is None:
        return {"class": "Safe", "reason": "No data", "estimated_mb": 0.0}
    n = len(counts.genome_ids)
    mb = (n * len(counts.features) * 8) / 1e6
    return {"class": "Safe", "reason": f"O(n*features) = {mb:.1f} MB", "estimated_mb": mb}
