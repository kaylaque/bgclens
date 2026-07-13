"""Extract Cluster profiles from a loaded BGCFlow Project."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bgclens.model import Project

from bgclens.model import Cluster

logger = logging.getLogger(__name__)

_CLUSTER_TYPE_KEYWORDS = {
    "nrps": "NRPS",
    "pks": "PKS",
    "t1pks": "PKS",
    "t2pks": "PKS",
    "t3pks": "PKS",
    "terpene": "terpene",
    "ripp": "RiPP",
    "lanthipeptide": "RiPP",
    "thiopeptide": "RiPP",
    "bacteriocin": "RiPP",
    "hybrid": "hybrid",
    "siderophore": "siderophore",
    "betalactone": "other",
    "ectoine": "other",
}


def _infer_type(gcf_id: str, source_row: dict) -> str:
    """Infer cluster type from GCF id or source row fields."""
    text = " ".join([
        gcf_id or "",
        str(source_row.get("class", "")),
        str(source_row.get("cluster_type", "")),
        str(source_row.get("bgc_class", "")),
    ]).lower()
    for kw, label in _CLUSTER_TYPE_KEYWORDS.items():
        if kw in text:
            return label
    return "unknown"


def _novelty_band(distance: float | None) -> str:
    """Map nearest-neighbour distance to a band label.

    Lower distance = more similar to known MIBiG entries = lower novelty.
    These are banded priors, not predictions.
    """
    if distance is None:
        return "low"
    if distance < 0.3:
        return "low"
    if distance < 0.6:
        return "medium"
    if distance < 0.85:
        return "high"
    return "novel-candidate"


def list_clusters(project: "Project") -> list[Cluster]:
    """Extract per-GCF cluster profiles from a loaded Project.

    Reads: presence_absence (GCF ids), taxonomy, network (for centrality),
    and bgc_novelty_retrieval.tsv (if present, for novelty band).
    Returns one Cluster per GCF id found in presence_absence.
    Deterministic — no LLM calls.
    """
    pa = project.gcf_presence_absence
    if pa is None:
        return []

    gcf_ids = pa.rows  # feature ids = GCF ids

    # Build organism lookup from taxonomy if available
    organism_by_genome: dict[str, str | None] = {}
    if project.taxonomy:
        tax = project.taxonomy
        for i, gid in enumerate(tax.genome_ids):
            genus = tax.genus[i] if i < len(tax.genus) else None
            species = tax.species[i] if i < len(tax.species) else None
            parts = [p for p in [genus, species] if p]
            organism_by_genome[gid] = " ".join(parts) if parts else None

    # Build centrality lookup from network (node degree as proxy)
    degree: dict[str, int] = {}
    if project.gcf_network:
        for src, tgt, _ in project.gcf_network.edges:
            degree[src] = degree.get(src, 0) + 1
            degree[tgt] = degree.get(tgt, 0) + 1

    # Load novelty retrieval file if present
    novelty_distances: dict[str, float] = {}
    if project.manifest.source_path:
        nov_path = project.manifest.source_path / "bgc_novelty_retrieval.tsv"
        if nov_path.exists():
            try:
                import csv
                with nov_path.open() as f:
                    reader = csv.DictReader(f, delimiter="\t")
                    for row in reader:
                        gcf_id = row.get("gcf_id") or row.get("GCF_ID") or ""
                        dist_str = row.get("nn_distance") or row.get("distance") or ""
                        if gcf_id and dist_str:
                            try:
                                novelty_distances[gcf_id] = float(dist_str)
                            except ValueError:
                                pass
            except Exception as e:
                logger.debug("novelty retrieval load failed: %s", e)

    # Find the most common organism for a GCF (genome with highest presence)
    genome_ids = pa.cols
    clusters: list[Cluster] = []
    for i, gcf_id in enumerate(gcf_ids):
        row_vals = pa.values[i] if i < len(pa.values) else []
        source_row: dict = {}
        if pa.row_meta and gcf_id in pa.row_meta:
            source_row = pa.row_meta[gcf_id] if isinstance(pa.row_meta, dict) else {}

        # Find most prevalent genome for this GCF
        organism: str | None = None
        if row_vals and organism_by_genome:
            best_idx = max(range(len(row_vals)), key=lambda j: row_vals[j] if j < len(row_vals) else 0)
            if best_idx < len(genome_ids):
                organism = organism_by_genome.get(genome_ids[best_idx])

        dist = novelty_distances.get(gcf_id)
        band = _novelty_band(dist)
        cluster_type = _infer_type(gcf_id, source_row)

        clusters.append(Cluster(
            cluster_id=gcf_id,
            gcf_id=gcf_id,
            cluster_type=cluster_type,
            organism=organism,
            novelty_band=band,
            novelty_distance=dist,
            source_row=source_row,
        ))

    return clusters


def select_smoke_clusters(clusters: list[Cluster], n: int = 3) -> list[Cluster]:
    """Select up to n clusters for a smoke round.

    Deterministic: prefers diverse types, then falls back to first n.
    """
    if not clusters or n <= 0:
        return []
    if len(clusters) <= n:
        return clusters[:]

    # Pick one cluster per type for diversity, then fill to n
    seen_types: set[str] = set()
    selected: list[Cluster] = []
    for c in clusters:
        if c.cluster_type not in seen_types:
            seen_types.add(c.cluster_type)
            selected.append(c)
        if len(selected) >= n:
            break

    # If we didn't get n unique types, fill from the front
    if len(selected) < n:
        for c in clusters:
            if c not in selected:
                selected.append(c)
            if len(selected) >= n:
                break

    return selected
