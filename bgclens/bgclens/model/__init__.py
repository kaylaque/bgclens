"""Canonical data model for BGCLens. All BGCFlow output is normalized into these types."""
from pathlib import Path
from typing import Any
import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, Field


class DatasetHandle(BaseModel):
    """Descriptor for a single available dataset within a BGCFlow project."""
    name: str
    source: str  # e.g. "bigscape", "antismash"
    shape: tuple[int, ...]  # (n_rows, n_cols) or (n_nodes, n_edges) etc.
    description: str = ""


class ProjectManifest(BaseModel):
    """Capabilities manifest produced by the adapter layer after inspecting a BGCFlow project."""
    project_name: str
    source_path: Path
    duckdb_path: Path | None = None
    available_pipelines: set[str] = Field(default_factory=set)
    datasets: dict[str, DatasetHandle] = Field(default_factory=dict)


class MetadataTable(BaseModel):
    """Join hub keyed by genome_id. Contains taxonomy and quality annotations."""
    genome_ids: list[str]
    columns: list[str]
    # rows[i] is a dict of column→value for genome_ids[i]
    rows: list[dict[str, Any]] = Field(default_factory=list)


class PresenceAbsenceMatrix(BaseModel):
    """Binary or integer matrix — rows=features (e.g. GCF ids), cols=genome ids."""
    rows: list[str]  # feature ids
    cols: list[str]  # genome ids
    # Store as nested list for JSON-serializability; convert to NDArray on use
    values: list[list[int]]
    row_meta: dict[str, Any] = Field(default_factory=dict)
    col_meta: MetadataTable | None = None

    def to_numpy(self) -> NDArray:
        return np.array(self.values, dtype=np.int8)


class FeatureCountTable(BaseModel):
    """Count of features per genome — e.g. BGC classes per genome."""
    genome_ids: list[str]
    features: list[str]
    counts: list[list[int]]  # shape: len(genome_ids) × len(features)

    def to_numpy(self) -> NDArray:
        return np.array(self.counts, dtype=np.int32)


class TaxonomyTable(BaseModel):
    """GTDB-Tk taxonomy per genome."""
    genome_ids: list[str]
    domain: list[str | None] = Field(default_factory=list)
    phylum: list[str | None] = Field(default_factory=list)
    class_: list[str | None] = Field(default_factory=list, alias="class")
    order: list[str | None] = Field(default_factory=list)
    family: list[str | None] = Field(default_factory=list)
    genus: list[str | None] = Field(default_factory=list)
    species: list[str | None] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class QualityTable(BaseModel):
    """CheckM quality metrics per genome."""
    genome_ids: list[str]
    completeness: list[float | None] = Field(default_factory=list)
    contamination: list[float | None] = Field(default_factory=list)
    strain_heterogeneity: list[float | None] = Field(default_factory=list)


class NetworkEdgeList(BaseModel):
    """Similarity network for GCFs or genomes."""
    nodes: list[str]
    # edges: list of (source, target, weight)
    edges: list[tuple[str, str, float]] = Field(default_factory=list)


class Project(BaseModel):
    """Fully loaded BGCFlow project ready for analysis."""
    manifest: ProjectManifest
    gcf_presence_absence: PresenceAbsenceMatrix | None = None
    bgc_counts: FeatureCountTable | None = None
    taxonomy: TaxonomyTable | None = None
    quality: QualityTable | None = None
    gcf_network: NetworkEdgeList | None = None
    metadata: MetadataTable | None = None


from typing import Literal


class Cluster(BaseModel):
    """A single BGC / GCF cluster profile extracted from a BGCFlow project."""
    cluster_id: str
    gcf_id: str | None = None
    cluster_type: str = "unknown"  # NRPS, PKS, terpene, RiPP, hybrid, unknown
    core_biosynthetic_genes: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    organism: str | None = None
    novelty_band: Literal["high", "medium", "low", "novel-candidate"] = "low"
    novelty_distance: float | None = None  # nearest-neighbour distance if available
    source_row: dict[str, Any] = Field(default_factory=dict)


class BatchEvent(BaseModel):
    """Live status update from run_batch()."""
    task_id: str
    cluster_id: str
    method_id: str
    state: Literal["queued", "running", "success", "failed"]
    error: str | None = None


class Turn(BaseModel):
    """One turn in a multi-turn chat session."""
    role: Literal["user", "assistant"]
    content: str
    mentions: list[str] = Field(default_factory=list)


class Mention(BaseModel):
    """A resolved @mention pointing at a Knowledge Base object."""
    raw: str         # e.g. "@cluster_1"
    object_id: str   # e.g. "cluster_1"
    object_type: str  # "cluster" | "method" | "report_section" | "dataset"
    context_snippet: str = ""  # deterministic text pulled from the KB object


class BatchReport(BaseModel):
    """Input to render_batch() — the full set of results from a run_batch call."""
    project_name: str
    records: list[Any]    # list[RunRecord] — Any to avoid circular import at model level
    summary: str = ""
    cluster_comparison: dict[str, Any] = Field(default_factory=dict)
