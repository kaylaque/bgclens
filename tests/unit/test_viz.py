"""Tests for visualization service."""
import pytest
import numpy as np
from bgclens.viz.recommend import recommend_chart
from bgclens.viz.render import render
from bgclens.viz.theme import color_cycle, OKABE_ITO


def test_color_cycle_colorblind_safe():
    colors = color_cycle(8)
    assert len(colors) == 8
    assert colors[0] == OKABE_ITO[0]


def test_recommend_pcoa():
    spec = recommend_chart({"method": "pcoa"})
    assert spec.chart_type == "scatter_ordination"
    assert len(spec.alternatives) >= 1


def test_recommend_unknown_method():
    spec = recommend_chart({"method": "unknown_xyz"})
    assert spec.chart_type == "generic_bar"


def _pcoa_result():
    return {
        "method": "pcoa",
        "genome_ids": ["g1", "g2", "g3", "g4", "g5"],
        "coordinates": [[0.1, 0.2], [-0.3, 0.1], [0.4, -0.2], [-0.1, -0.3], [0.2, 0.3]],
        "explained_variance_pct": [35.2, 22.1],
        "n_components": 2,
        "subsampled": False,
        "n_genomes": 5,
    }


def _diversity_result():
    return {
        "method": "alpha_diversity",
        "metrics": ["shannon", "simpson"],
        "results": [
            {"genome_id": "g1", "shannon": 1.2, "simpson": 0.7},
            {"genome_id": "g2", "shannon": 0.9, "simpson": 0.6},
            {"genome_id": "g3", "shannon": 1.5, "simpson": 0.8},
        ],
        "n_genomes": 3,
    }


def _enrichment_result():
    return {
        "method": "fisher_exact",
        "features": ["terpene", "nrps", "pks"],
        "pvalues_adj": [0.01, 0.5, 0.03],
        "odds_ratios": [2.3, 0.8, 3.1],
        "significant_features": ["terpene", "pks"],
        "alpha": 0.05,
        "groups": ["A", "B"],
    }


def test_render_pcoa_returns_bytes():
    svg, png = render(_pcoa_result())
    assert svg.startswith(b"<?xml") or b"<svg" in svg
    assert png[:4] == b"\x89PNG"


def test_render_diversity_returns_bytes():
    svg, png = render(_diversity_result())
    assert b"<svg" in svg or svg.startswith(b"<?xml")
    assert len(png) > 100


def test_render_enrichment_returns_bytes():
    svg, png = render(_enrichment_result())
    assert len(svg) > 100
    assert len(png) > 100


def test_render_unknown_method_fallback():
    svg, png = render({"method": "unknown_method", "some_key": "some_val"})
    assert len(svg) > 0
    assert len(png) > 0


def test_render_dendrogram():
    from bgclens.catalog.methods.clustering import run as cluster_run
    from bgclens.model import PresenceAbsenceMatrix
    pa = PresenceAbsenceMatrix(
        rows=["GCF_1", "GCF_2", "GCF_3"],
        cols=["g1", "g2", "g3", "g4", "g5"],
        values=[[1, 0, 1, 0, 1], [0, 1, 1, 1, 0], [1, 1, 0, 0, 1]],
    )
    result = cluster_run({"presence_absence": pa}, {"n_clusters": 2})
    svg, png = render(result)
    assert len(svg) > 0
