"""Lighter-alternative mapping and trade-off descriptions for the compute advisor."""

# Maps method_id → list of (alternative_method_id, trade_off_description)
# Ordered from cheapest to slightly-more-expensive alternatives within the same intent.
LIGHTER_ALTERNATIVES: dict[str, list[tuple[str, str]]] = {
    "permanova": [
        ("pcoa", "PCoA visualises the same distance structure at O(N²) cost but does not give a p-value for group separation; use PERMANOVA on a subsample for significance."),
    ],
    "pcoa": [
        ("pca", "PCA operates on raw counts (not distances) and is O(N·F), so much faster; trade-off: Euclidean geometry may distort presence/absence data."),
    ],
    "hierarchical_clustering": [
        ("pcoa", "PCoA provides a lower-dimensional ordination with similar distance structure at comparable cost."),
    ],
    "louvain_community": [],  # Already lightweight for most graph sizes
    "fisher_enrichment": [],  # O(N·F), always cheap
    "alpha_diversity": [],    # O(N·F), always cheap
    "pca": [],
}


def trade_off_for(method_id: str, alternative_id: str) -> str:
    """Return a human-readable trade-off description, or a generic fallback."""
    for alt_id, desc in LIGHTER_ALTERNATIVES.get(method_id, []):
        if alt_id == alternative_id:
            return desc
    return f"{alternative_id} is lighter but may sacrifice some analytical resolution."
