"""Engine-side matplotlib renderers. All return (svg_bytes: bytes, png_bytes: bytes)."""
from __future__ import annotations
import io
from typing import Any

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from bgclens.viz.theme import apply_theme, color_cycle
from bgclens.viz.recommend import recommend_chart


def render(result: dict[str, Any], metadata: Any = None) -> tuple[bytes, bytes]:
    """Dispatch to the correct renderer based on result['method']. Returns (svg, png)."""
    apply_theme()
    method = result.get("method", "")
    dispatch = {
        "pcoa": render_ordination,
        "pca": render_ordination,
        "permanova": render_permanova,
        "fisher_exact": render_enrichment,
        "alpha_diversity": render_diversity,
        "hierarchical_clustering": render_dendrogram,
        "louvain_community": render_community,
    }
    fn = dispatch.get(method, render_generic)
    fig = fn(result, metadata)
    svg = _to_bytes(fig, "svg")
    png = _to_bytes(fig, "png")
    plt.close(fig)
    return svg, png


def _to_bytes(fig, fmt: str) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, bbox_inches="tight", dpi=150)
    buf.seek(0)
    return buf.read()


def _group_colors(genome_ids: list[str], metadata: Any) -> dict[str, str]:
    """Map genome_id → color based on metadata grouping (first non-genome_id column)."""
    if metadata is None or not hasattr(metadata, "rows"):
        return {gid: color_cycle(1)[0] for gid in genome_ids}
    # Find first grouping column
    cols = [c for c in (getattr(metadata, "columns", []) or []) if c != "genome_id"]
    if not cols:
        return {gid: color_cycle(1)[0] for gid in genome_ids}
    col = cols[0]
    id_to_group = {row.get("genome_id"): row.get(col) for row in metadata.rows}
    unique_groups = sorted({v for v in id_to_group.values() if v is not None})
    group_to_color = {g: color_cycle(len(unique_groups))[i] for i, g in enumerate(unique_groups)}
    return {gid: group_to_color.get(id_to_group.get(gid), "#888888") for gid in genome_ids}


def render_ordination(result: dict, metadata: Any) -> plt.Figure:
    """Scatter plot of first 2 coordinates."""
    genome_ids = result.get("genome_ids", [])
    coords = np.array(result.get("coordinates", []))
    explained = result.get("explained_variance_pct", [])
    method = result.get("method", "ordination").upper()

    fig, ax = plt.subplots(figsize=(7, 5))

    colors = _group_colors(genome_ids, metadata)
    xs = coords[:, 0] if coords.ndim > 1 and coords.shape[1] > 0 else np.zeros(len(genome_ids))
    ys = coords[:, 1] if coords.ndim > 1 and coords.shape[1] > 1 else np.zeros(len(genome_ids))

    color_list = [colors.get(gid, "#888888") for gid in genome_ids]
    ax.scatter(xs, ys, c=color_list, s=60, alpha=0.85, edgecolors="white", linewidths=0.5)

    x_pct = f" ({explained[0]:.1f}%)" if explained else ""
    y_pct = f" ({explained[1]:.1f}%)" if len(explained) > 1 else ""
    ax.set_xlabel(f"PC1{x_pct}")
    ax.set_ylabel(f"PC2{y_pct}")
    ax.set_title(f"{method} ordination (n={len(genome_ids)} genomes)")

    # Legend for groups
    if metadata and hasattr(metadata, "rows"):
        cols = [c for c in (getattr(metadata, "columns", []) or []) if c != "genome_id"]
        if cols:
            col = cols[0]
            id_to_group = {row.get("genome_id"): row.get(col) for row in metadata.rows}
            unique_groups = sorted({v for v in id_to_group.values() if v is not None})
            group_to_color = {g: color_cycle(len(unique_groups))[i] for i, g in enumerate(unique_groups)}
            patches = [mpatches.Patch(color=c, label=str(g)) for g, c in group_to_color.items()]
            ax.legend(handles=patches, title=col, fontsize=9, title_fontsize=9)

    if result.get("subsampled"):
        ax.text(0.01, 0.01, f"Subsampled to {len(genome_ids)} genomes",
                transform=ax.transAxes, fontsize=8, color="#888888")
    fig.tight_layout()
    return fig


def render_permanova(result: dict, metadata: Any) -> plt.Figure:
    """PERMANOVA result: show group separation info as a text figure with ordination if coords available."""
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.axis("off")
    p = result.get("pvalue", float("nan"))
    f = result.get("test_statistic", float("nan"))
    n = result.get("n_genomes", "?")
    groups = result.get("groups", [])
    text = (
        f"PERMANOVA result\n\n"
        f"Groups: {', '.join(str(g) for g in groups)}\n"
        f"F-statistic: {f:.4f}\n"
        f"p-value: {p:.4f}\n"
        f"N genomes: {n}\n"
        f"Permutations: {result.get('permutations', '?')}"
    )
    ax.text(0.1, 0.5, text, transform=ax.transAxes, fontsize=12,
            verticalalignment="center", family="monospace",
            bbox=dict(boxstyle="round", facecolor="#f0f4ff", alpha=0.8))
    ax.set_title("PERMANOVA")
    fig.tight_layout()
    return fig


def render_enrichment(result: dict, metadata: Any) -> plt.Figure:
    """Dot plot for enrichment results."""
    features = result.get("features", [])
    pvals = result.get("pvalues_adj", [])
    ors = result.get("odds_ratios", [])
    alpha = result.get("alpha", 0.05)

    if not features:
        return _empty_figure("No enrichment features")

    fig, ax = plt.subplots(figsize=(7, max(4, len(features) * 0.4 + 1)))

    neg_log_p = [-np.log10(max(p, 1e-300)) if p is not None else 0 for p in pvals]
    sig_mask = [p is not None and p <= alpha for p in pvals]
    colors = [color_cycle(2)[0] if s else "#cccccc" for s in sig_mask]
    sizes = [max(30, nlp * 20) for nlp in neg_log_p]

    y_pos = list(range(len(features)))
    ax.scatter(ors, y_pos, c=colors, s=sizes, alpha=0.85, edgecolors="white", linewidths=0.5)
    ax.axvline(1.0, color="#888888", linestyle="--", linewidth=0.8)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(features, fontsize=9)
    ax.set_xlabel("Odds Ratio")
    ax.set_title(f"BGC class enrichment (adj. p ≤ {alpha})")

    sig_patch = mpatches.Patch(color=color_cycle(2)[0], label=f"Significant (adj. p≤{alpha})")
    ns_patch = mpatches.Patch(color="#cccccc", label="Not significant")
    ax.legend(handles=[sig_patch, ns_patch], fontsize=9)
    fig.tight_layout()
    return fig


def render_diversity(result: dict, metadata: Any) -> plt.Figure:
    """Bar chart of alpha diversity per genome."""
    records = result.get("results", [])
    metrics = result.get("metrics", ["shannon"])

    if not records:
        return _empty_figure("No diversity data")

    n_metrics = len(metrics)
    fig, axes = plt.subplots(1, n_metrics, figsize=(5 * n_metrics, 5), squeeze=False)

    for idx, metric in enumerate(metrics):
        ax = axes[0][idx]
        vals = [r.get(metric, 0) for r in records]
        gids = [records[i].get("genome_id", str(i)) for i in range(len(records))]
        cols = color_cycle(len(vals))
        ax.bar(range(len(vals)), vals, color=cols, alpha=0.85, edgecolor="white")
        ax.set_xticks(range(len(gids)))
        ax.set_xticklabels(gids, rotation=60, ha="right", fontsize=7)
        ax.set_ylabel(f"{metric.capitalize()} index")
        ax.set_title(f"{metric.capitalize()} diversity")

    fig.suptitle("Alpha Diversity", fontsize=13)
    fig.tight_layout()
    return fig


def render_dendrogram(result: dict, metadata: Any) -> plt.Figure:
    """Hierarchical clustering dendrogram."""
    from scipy.cluster.hierarchy import dendrogram

    Z = result.get("linkage_matrix")
    genome_ids = result.get("genome_ids", [])

    if not Z:
        return _empty_figure("No linkage matrix")

    fig, ax = plt.subplots(figsize=(max(8, len(genome_ids) * 0.3), 5))
    dendrogram(
        np.array(Z),
        labels=genome_ids,
        ax=ax,
        leaf_rotation=60,
        leaf_font_size=7,
        color_threshold=0,
        above_threshold_color=color_cycle(1)[0],
    )
    ax.set_title(f"Hierarchical clustering ({result.get('linkage', 'ward')} linkage)")
    ax.set_ylabel("Distance")
    fig.tight_layout()
    return fig


def render_community(result: dict, metadata: Any) -> plt.Figure:
    """Bar chart of community sizes from Louvain."""
    sizes = result.get("community_sizes", {})
    modularity = result.get("modularity", 0.0)

    if not sizes:
        return _empty_figure("No community data")

    communities = sorted(sizes.keys())
    counts = [sizes[c] for c in communities]
    cols = color_cycle(len(communities))

    fig, ax = plt.subplots(figsize=(max(6, len(communities)), 4))
    ax.bar(range(len(communities)), counts, color=cols, alpha=0.85, edgecolor="white")
    ax.set_xticks(range(len(communities)))
    ax.set_xticklabels([f"C{c}" for c in communities], fontsize=9)
    ax.set_ylabel("Number of GCFs")
    ax.set_title(f"Louvain communities (Q={modularity:.3f}, {result.get('n_communities', '?')} communities)")
    fig.tight_layout()
    return fig


def render_generic(result: dict, metadata: Any) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.axis("off")
    summary = "\n".join(f"{k}: {v}" for k, v in result.items() if not isinstance(v, (list, dict)))
    ax.text(0.05, 0.5, summary or "No result data", transform=ax.transAxes,
            fontsize=10, verticalalignment="center", family="monospace")
    fig.tight_layout()
    return fig


def _empty_figure(message: str) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes, fontsize=12)
    return fig
