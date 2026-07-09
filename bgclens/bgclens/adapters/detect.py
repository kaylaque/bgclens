"""Detect which BGCFlow pipelines produced output and build a ProjectManifest."""
from pathlib import Path
from bgclens.model import DatasetHandle, ProjectManifest

# Known BGCFlow output file patterns, keyed by pipeline name
_PIPELINE_MARKERS: dict[str, list[str]] = {
    "antismash": ["tables/df_antismash_7.0.1_summary.csv"],
    "bigscape": [
        "bigscape/network_files",
        "tables/df_bigscape_cluster_summary.csv",
    ],
    "bigslice": ["tables/df_bigslice_query_network_annotated.csv"],
    "gecco": ["tables/df_gecco_features.csv"],
    "checkm": ["tables/df_checkm_quality.csv"],
    "gtdbtk": ["tables/df_gtdb_meta.csv"],
    "arts": ["tables/df_arts_genbank_table.csv"],
    "roary": ["tables/df_roary_presence_absence.csv"],
    "mash": ["tables/df_mash_triangle.csv"],
}

_DUCKDB_NAMES = ["dbt_bgcflow.duckdb", "bgcflow.duckdb"]


def detect_project(path: Path) -> ProjectManifest:
    """Scan a BGCFlow processed project directory and return a ProjectManifest.

    Raises:
        ValueError: if the path does not look like a valid BGCFlow project.
    """
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Path does not exist or is not a directory: {path}")

    available: set[str] = set()
    for pipeline, markers in _PIPELINE_MARKERS.items():
        for marker in markers:
            if (path / marker).exists():
                available.add(pipeline)
                break

    # Detect DuckDB
    duckdb_path: Path | None = None
    for name in _DUCKDB_NAMES:
        candidate = path / name
        if candidate.exists():
            duckdb_path = candidate
            break

    if not available and duckdb_path is None:
        raise ValueError(
            f"No BGCFlow pipeline output found at {path}. "
            "Expected tables/ subdirectory or DuckDB file."
        )

    datasets: dict[str, DatasetHandle] = {}
    for pipeline in available:
        datasets[pipeline] = DatasetHandle(
            name=pipeline,
            source=pipeline,
            shape=(0,),
            description=f"{pipeline} output detected",
        )

    return ProjectManifest(
        project_name=path.name,
        source_path=path,
        duckdb_path=duckdb_path,
        available_pipelines=available,
        datasets=datasets,
    )
