"""Map (result_type × intent) to recommended chart type."""
from dataclasses import dataclass


@dataclass
class ChartSpec:
    chart_type: str           # e.g. "scatter_ordination"
    title: str
    alternatives: list[str]   # alternative chart types for this result
    description: str


# Lookup by result["method"] value
_METHOD_TO_CHART: dict[str, ChartSpec] = {
    "pcoa": ChartSpec(
        chart_type="scatter_ordination",
        title="PCoA Ordination",
        alternatives=["heatmap_distance"],
        description="Grouped scatter of first two principal coordinates.",
    ),
    "pca": ChartSpec(
        chart_type="scatter_ordination",
        title="PCA Ordination",
        alternatives=["biplot"],
        description="Grouped scatter of first two principal components.",
    ),
    "fisher_exact": ChartSpec(
        chart_type="dot_enrichment",
        title="BGC Class Enrichment",
        alternatives=["bar_enrichment"],
        description="Dot plot: x=odds ratio, y=feature, size=−log10(p), color=significance.",
    ),
    "alpha_diversity": ChartSpec(
        chart_type="bar_diversity",
        title="Alpha Diversity",
        alternatives=["violin_diversity"],
        description="Bar chart of Shannon/Simpson diversity per genome.",
    ),
    "hierarchical_clustering": ChartSpec(
        chart_type="dendrogram",
        title="Genome Clustering Dendrogram",
        alternatives=["heatmap_clustering"],
        description="Dendrogram of hierarchical clustering.",
    ),
    "louvain_community": ChartSpec(
        chart_type="bar_community",
        title="Community Sizes",
        alternatives=["pie_community"],
        description="Bar chart of community sizes from Louvain detection.",
    ),
    "permanova": ChartSpec(
        chart_type="scatter_ordination",
        title="PCoA with PERMANOVA Groups",
        alternatives=["bar_permanova"],
        description="Ordination scatter coloured by group (PERMANOVA result annotated).",
    ),
}


def recommend_chart(result: dict) -> ChartSpec:
    """Return the recommended chart spec for a method result."""
    method = result.get("method", "")
    if method in _METHOD_TO_CHART:
        return _METHOD_TO_CHART[method]
    return ChartSpec(
        chart_type="generic_bar",
        title="Analysis Result",
        alternatives=[],
        description="Generic result visualization.",
    )
