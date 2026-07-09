"""DuckDB reader for BGCFlow's OLAP database (read-only)."""
from pathlib import Path
import duckdb
import pandas as pd
from bgclens.model import MetadataTable, PresenceAbsenceMatrix, TaxonomyTable


def _open(db_path: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path), read_only=True)


def load_gcf_presence_absence(db_path: Path) -> PresenceAbsenceMatrix | None:
    """Try to load GCF presence/absence from DuckDB. Returns None if the table is absent."""
    try:
        con = _open(db_path)
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "df_bigscape_cluster_summary" not in tables:
            return None
        df: pd.DataFrame = con.execute(
            "SELECT * FROM df_bigscape_cluster_summary"
        ).df()
        con.close()
        if df.empty:
            return None
        genome_cols = [c for c in df.columns if c not in ("gcf_id", "index")]
        gcf_ids = df.iloc[:, 0].astype(str).tolist()
        values = df[genome_cols].fillna(0).astype(int).values.tolist()
        return PresenceAbsenceMatrix(rows=gcf_ids, cols=genome_cols, values=values)
    except Exception:
        return None


def load_taxonomy(db_path: Path) -> TaxonomyTable | None:
    """Try to load GTDB taxonomy from DuckDB."""
    try:
        con = _open(db_path)
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "df_gtdb_meta" not in tables:
            return None
        df = con.execute("SELECT * FROM df_gtdb_meta").df()
        con.close()
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
    except Exception:
        return None
