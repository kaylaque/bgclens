"""CSV/TSV fallback loaders for BGCFlow outputs."""
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


def load_gcf_presence_absence(project_path: Path) -> PresenceAbsenceMatrix | None:
    """Load BiG-SCAPE GCF presence/absence matrix from CSV."""
    candidates = [
        project_path / "tables" / "df_bigscape_cluster_summary.csv",
        project_path / "bigscape" / "presence_absence.csv",
    ]
    for p in candidates:
        if p.exists():
            df = _read_table(p, index_col=0)
            genome_ids = list(df.columns)
            gcf_ids = list(df.index.astype(str))
            values = df.fillna(0).astype(int).values.tolist()
            return PresenceAbsenceMatrix(rows=gcf_ids, cols=genome_ids, values=values)
    return None


def load_bgc_counts(project_path: Path) -> FeatureCountTable | None:
    """Load BGC-class count per genome from antiSMASH summary CSV."""
    p = project_path / "tables" / "df_antismash_7.0.1_summary.csv"
    if not p.exists():
        return None
    df = _read_table(p)
    if "genome_id" not in df.columns:
        return None
    genome_ids = df["genome_id"].tolist()
    feature_cols = [c for c in df.columns if c not in ("genome_id",)]
    counts = df[feature_cols].fillna(0).astype(int).values.tolist()
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
