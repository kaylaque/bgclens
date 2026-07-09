"""CSV/TSV fallback loaders for BGCFlow outputs."""
import os
from pathlib import Path
import pandas as pd
from bgclens.model import (
    FeatureCountTable,
    MetadataTable,
    PresenceAbsenceMatrix,
    QualityTable,
    TaxonomyTable,
)


def _read_table(path: Path, **kwargs) -> pd.DataFrame:
    sep = "\t" if path.suffix in (".tsv", ".txt") else ","
    return pd.read_csv(path, sep=sep, **kwargs)


def find_antismash_summary(project_path: Path) -> Path | None:
    """Locate the antiSMASH summary table, whichever antiSMASH version produced it.

    BGCFlow embeds the antiSMASH version in the filename (e.g. 7.1.0, 8.0.4),
    so the version cannot be hardcoded. Newest version wins when several exist.
    """
    matches = sorted(
        (project_path / "tables").glob("df_antismash_*_summary.csv"),
        key=lambda p: _version_key(p.name),
    )
    return matches[-1] if matches else None


def _version_key(name: str) -> tuple[int, ...]:
    version = name[len("df_antismash_"):-len("_summary.csv")]
    parts = []
    for chunk in version.split("."):
        parts.append(int(chunk) if chunk.isdigit() else 0)
    return tuple(parts)


# BiG-SCAPE's canonical default GCF distance cutoff. BGCFlow emits one matrix
# per cutoff (0.3/0.4/0.5) and pins none of them, so pick 0.3 unless overridden.
_DEFAULT_BIGSCAPE_CUTOFF = "0.3"


def _find_bigscape2_family_presence(project_path: Path) -> Path | None:
    """Locate BiG-SCAPE 2's family-presence matrix.

    BGCFlow writes it as
      bigscape2/for_cytoscape_antismash_<ver>/<timestamp>_df_family_presence_<cutoff>.csv
    so both the antiSMASH version and the run timestamp are unpredictable.
    """
    cutoff = os.environ.get("BGCLENS_BIGSCAPE_CUTOFF", _DEFAULT_BIGSCAPE_CUTOFF)
    matches = sorted(
        project_path.glob(f"bigscape2/*/*df_family_presence_{cutoff}.csv")
    )
    return matches[-1] if matches else None  # newest timestamp wins


def load_gcf_presence_absence(project_path: Path) -> PresenceAbsenceMatrix | None:
    """Load the BiG-SCAPE GCF presence/absence matrix."""
    # Legacy / BiG-SCAPE 1 layouts: already gcf-by-genome.
    for p in (
        project_path / "tables" / "df_bigscape_cluster_summary.csv",
        project_path / "bigscape" / "presence_absence.csv",
    ):
        if p.exists():
            df = _read_table(p, index_col=0)
            genome_ids = list(df.columns)
            gcf_ids = list(df.index.astype(str))
            values = df.fillna(0).astype(int).values.tolist()
            return PresenceAbsenceMatrix(rows=gcf_ids, cols=genome_ids, values=values)

    # BiG-SCAPE 2 layout: genome-by-family, i.e. transposed relative to ours.
    p = _find_bigscape2_family_presence(project_path)
    if p is None:
        return None

    df = _read_table(p, index_col=0)
    # BGCFlow emits a literal "nan" column for BGCs assigned to no family.
    df = df.drop(columns=[c for c in df.columns if str(c).strip().lower() == "nan"])
    if df.empty or df.shape[1] == 0:
        return None

    df = df.fillna(0).astype(int).T  # -> rows: families, cols: genomes
    return PresenceAbsenceMatrix(
        rows=[str(i) for i in df.index],
        cols=[str(c) for c in df.columns],
        values=df.values.tolist(),
    )


# Sample metadata BGCFlow carries through into the antiSMASH summary. These are
# strings, not counts.
_IDENTITY_COLS = frozenset({
    "genome_id", "source", "organism", "genus", "species", "strain",
    "closest_placement_reference", "input_file",
})

# Per-genome totals. Numeric, but they sum the per-class columns, so counting
# them as features would double-count every BGC.
_AGGREGATE_COLS = frozenset({
    "bgcs_count", "bgcs_on_contig_edge", "protoclusters_count",
    "cand_clusters_count",
})


def load_bgc_counts(project_path: Path) -> FeatureCountTable | None:
    """Load per-genome BGC-class counts from the antiSMASH summary CSV.

    Everything that is neither identity metadata nor a precomputed total is
    treated as a BGC class, since the class columns are named after whatever
    antiSMASH detected in this dataset and cannot be enumerated ahead of time.
    """
    p = find_antismash_summary(project_path)
    if p is None:
        return None
    df = _read_table(p)
    if "genome_id" not in df.columns:
        return None

    candidates = [
        c for c in df.columns
        if c not in _IDENTITY_COLS and c not in _AGGREGATE_COLS
    ]
    numeric = df[candidates].apply(pd.to_numeric, errors="coerce")
    # A candidate that coerces entirely to NaN is an unrecognised text column.
    feature_cols = [c for c in candidates if not numeric[c].isna().all()]
    if not feature_cols:
        return None

    genome_ids = df["genome_id"].tolist()
    counts = numeric[feature_cols].fillna(0).astype(int).values.tolist()
    return FeatureCountTable(genome_ids=genome_ids, features=feature_cols, counts=counts)


def load_taxonomy(project_path: Path) -> TaxonomyTable | None:
    """Load GTDB-Tk taxonomy from CSV."""
    p = project_path / "tables" / "df_gtdb_meta.csv"
    if not p.exists():
        return None
    df = _read_table(p)
    if "genome_id" not in df.columns:
        return None
    col_map = {
        "domain": "domain", "phylum": "phylum", "class": "class_",
        "order": "order", "family": "family", "genus": "genus", "species": "species",
    }
    kwargs: dict = {"genome_ids": df["genome_id"].tolist()}
    for csv_col, field in col_map.items():
        if csv_col in df.columns:
            kwargs[field] = df[csv_col].where(df[csv_col].notna(), None).tolist()
    return TaxonomyTable(**kwargs)


def load_quality(project_path: Path) -> QualityTable | None:
    """Load CheckM quality metrics from CSV."""
    p = project_path / "tables" / "df_checkm_quality.csv"
    if not p.exists():
        return None
    df = _read_table(p)
    if "genome_id" not in df.columns:
        return None
    return QualityTable(
        genome_ids=df["genome_id"].tolist(),
        completeness=df.get("completeness", pd.Series()).where(
            df.get("completeness", pd.Series()).notna(), None
        ).tolist() if "completeness" in df.columns else [],
        contamination=df.get("contamination", pd.Series()).where(
            df.get("contamination", pd.Series()).notna(), None
        ).tolist() if "contamination" in df.columns else [],
    )


def load_metadata(project_path: Path) -> MetadataTable | None:
    """Build a MetadataTable joining taxonomy + quality on genome_id."""
    tax = load_taxonomy(project_path)
    if tax is None:
        return None
    genome_ids = tax.genome_ids
    rows = [{"genome_id": gid} for gid in genome_ids]
    columns = ["genome_id", "domain", "phylum", "order", "family", "genus", "species"]
    for i, gid in enumerate(genome_ids):
        for attr in ("domain", "phylum", "order", "family", "genus", "species"):
            vals = getattr(tax, attr, [])
            rows[i][attr] = vals[i] if i < len(vals) else None
    return MetadataTable(genome_ids=genome_ids, columns=columns, rows=rows)
