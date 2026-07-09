"""Tests for CSV loaders against BGCFlow's real output shape."""
from pathlib import Path

from bgclens.adapters.csv_adapter import load_bgc_counts

# Header and first rows copied from a real BGCFlow run
# (data/processed/Lactobacillus_delbrueckii/tables/df_antismash_8.0.4_summary.csv).
# The metadata columns are what broke the naive "everything but genome_id is a
# count" assumption: `source` holds the string "ncbi".
_REAL_SUMMARY = (
    "genome_id,source,organism,genus,species,strain,closest_placement_reference,"
    "input_file,bgcs_count,bgcs_on_contig_edge,protoclusters_count,"
    "cand_clusters_count,lanthipeptide-class-iii,RiPP-like,terpene-precursor,"
    "lanthipeptide-class-iv\n"
    "GCA_000056065.1,ncbi,,,,,,,4.0,0.0,0.0,0.0,1.0,1.0,1.0,1.0\n"
    "GCA_000014405.1,ncbi,,,,,,,3.0,1.0,0.0,0.0,0.0,2.0,1.0,0.0\n"
)


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "tables" / "df_antismash_8.0.4_summary.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return tmp_path


def test_load_bgc_counts_ignores_string_metadata(tmp_path):
    """String metadata columns must not be coerced to int."""
    table = load_bgc_counts(_write(tmp_path, _REAL_SUMMARY))
    assert table is not None
    assert "source" not in table.features
    assert "organism" not in table.features


def test_load_bgc_counts_excludes_aggregate_totals(tmp_path):
    """bgcs_count and friends are totals, not per-class features."""
    table = load_bgc_counts(_write(tmp_path, _REAL_SUMMARY))
    for total in ("bgcs_count", "bgcs_on_contig_edge", "protoclusters_count",
                  "cand_clusters_count"):
        assert total not in table.features


def test_load_bgc_counts_keeps_bgc_classes(tmp_path):
    table = load_bgc_counts(_write(tmp_path, _REAL_SUMMARY))
    assert table.features == [
        "lanthipeptide-class-iii", "RiPP-like", "terpene-precursor",
        "lanthipeptide-class-iv",
    ]
    assert table.genome_ids == ["GCA_000056065.1", "GCA_000014405.1"]
    assert table.counts == [[1, 1, 1, 1], [0, 2, 1, 0]]


def test_load_bgc_counts_absent_returns_none(tmp_path):
    assert load_bgc_counts(tmp_path) is None


def test_load_bgc_counts_metadata_only_returns_none(tmp_path):
    """A summary with no class columns yields no feature table."""
    text = "genome_id,source,bgcs_count\nGCA_1,ncbi,4.0\n"
    assert load_bgc_counts(_write(tmp_path, text)) is None
