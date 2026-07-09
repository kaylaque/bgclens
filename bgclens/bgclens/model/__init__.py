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
