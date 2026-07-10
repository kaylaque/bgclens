"""Catalog validation and method smoke tests."""
import pytest
from bgclens.catalog.registry import load_catalog, validate_catalog, get_impl, methods_for_intent
from bgclens.model import PresenceAbsenceMatrix, FeatureCountTable


def test_catalog_loads():
    catalog = load_catalog()
    assert len(catalog) >= 6


def test_catalog_sq_tags_are_lists():
    """All catalog entries that declare sq: have it as a list."""
    catalog = load_catalog()
    for method_id, entry in catalog.items():
        if "sq" in entry:
            assert isinstance(entry["sq"], list), f"{method_id}: sq must be a list"


def test_catalog_valid():
    errors = validate_catalog()
    assert errors == [], "Catalog errors:\n" + "\n".join(errors)


def test_methods_for_enrichment():
    methods = methods_for_intent("enrichment")
    assert any(m["id"] == "fisher_enrichment" for m in methods)


def test_methods_for_ordination():
    methods = methods_for_intent("ordination")
    ids = [m["id"] for m in methods]
    assert "pcoa" in ids
    assert "pca" in ids


def test_methods_for_sq3_prioritization():
    methods = methods_for_intent("sq3_prioritization")
    ids = [m["id"] for m in methods]
    assert "pcoa" in ids
    assert "hierarchical_clustering" in ids


def test_methods_for_sq7_association():
    methods = methods_for_intent("sq7_association")
    ids = [m["id"] for m in methods]
    assert "permanova" in ids


def test_sq_intents_consistent_with_intents_list():
    """sq: tags are a subset of each entry's intents: list."""
    catalog = load_catalog()
    for method_id, entry in catalog.items():
        sq_tags = entry.get("sq", [])
        intents_list = entry.get("intents", [])
        for sq in sq_tags:
            assert sq in intents_list, (
                f"{method_id}: sq tag '{sq}' not found in intents list {intents_list}"
            )


def _dummy_pa():
    return PresenceAbsenceMatrix(
        rows=["GCF_1", "GCF_2", "GCF_3"],
        cols=["g1", "g2", "g3", "g4", "g5"],
        values=[[1, 0, 1, 0, 1], [0, 1, 1, 1, 0], [1, 1, 0, 0, 1]],
    )


def _dummy_counts():
    return FeatureCountTable(
        genome_ids=["g1", "g2", "g3", "g4", "g5"],
        features=["terpene", "nrps", "pks"],
        counts=[[3, 1, 0], [0, 2, 1], [1, 0, 2], [2, 1, 1], [0, 3, 0]],
    )


def test_pcoa_runs():
    run_fn, _, _ = get_impl("pcoa")
    result = run_fn({"presence_absence": _dummy_pa()}, {"n_components": 2})
    assert "coordinates" in result
    assert len(result["coordinates"]) == 5


def test_pca_runs():
    run_fn, _, _ = get_impl("pca")
    result = run_fn({"counts": _dummy_counts()}, {"n_components": 2})
    assert "coordinates" in result


def test_diversity_runs():
    run_fn, _, _ = get_impl("alpha_diversity")
    result = run_fn({"counts": _dummy_counts()}, {"metrics": ["shannon", "simpson"]})
    assert result["n_genomes"] == 5
    assert "mean_shannon" in result


def test_clustering_runs():
    run_fn, _, _ = get_impl("hierarchical_clustering")
    result = run_fn({"presence_absence": _dummy_pa()}, {"n_clusters": 2})
    assert result["n_genomes"] == 5
    assert result["cluster_labels"] is not None


def test_enrichment_runs():
    from bgclens.model import MetadataTable

    counts = _dummy_counts()
    metadata = MetadataTable(
        genome_ids=counts.genome_ids,
        columns=["genome_id", "clade"],
        rows=[
            {"genome_id": "g1", "clade": "A"},
            {"genome_id": "g2", "clade": "A"},
            {"genome_id": "g3", "clade": "B"},
            {"genome_id": "g4", "clade": "B"},
            {"genome_id": "g5", "clade": "B"},
        ],
    )
    run_fn, _, _ = get_impl("fisher_enrichment")
    result = run_fn({"counts": counts, "metadata": metadata}, {"grouping_col": "clade"})
    assert "pvalues_raw" in result
    assert len(result["pvalues_raw"]) == 3
