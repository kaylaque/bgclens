"""Stage 1: deterministic extraction of InterpretationFacts from a method result dict."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InterpretationFacts:
    method_id: str
    n_samples: int
    result_summary: str        # one-line plain-language summary of the result
    key_numbers: dict[str, float]  # the only numbers the LLM may reference
    significant: bool
    direction: str             # e.g. "enriched in group A", "separated", "diverse"
    caveats: list[str] = field(default_factory=list)
    what_it_does_not_tell_you: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    assumption_warnings: list[str] = field(default_factory=list)


def extract_facts(result: dict[str, Any], assumption_warnings: list[str] | None = None) -> InterpretationFacts:
    """Dispatch to the correct extractor based on result['method']."""
    method = result.get("method", "")
    warnings = assumption_warnings or []

    extractors = {
        "pcoa": _facts_ordination,
        "pca": _facts_ordination,
        "fisher_exact": _facts_enrichment,
        "alpha_diversity": _facts_diversity,
        "hierarchical_clustering": _facts_clustering,
        "louvain_community": _facts_community,
        "permanova": _facts_permanova,
    }
    fn = extractors.get(method, _facts_generic)
    facts = fn(result)
    facts.assumption_warnings = warnings
    facts.caveats.extend(warnings)
    return facts


def _facts_ordination(result: dict) -> InterpretationFacts:
    n = result.get("n_genomes", len(result.get("genome_ids", [])))
    explained = result.get("explained_variance_pct", [])
    pc1 = explained[0] if explained else 0.0
    pc2 = explained[1] if len(explained) > 1 else 0.0
    sub = result.get("subsampled", False)

    return InterpretationFacts(
        method_id=result.get("method", "ordination"),
        n_samples=n,
        result_summary=(
            f"PCoA ordination of {n} genomes; PC1 explains {pc1:.1f}% and PC2 {pc2:.1f}% of variance."
        ),
        key_numbers={"pc1_variance_pct": pc1, "pc2_variance_pct": pc2, "n_genomes": float(n)},
        significant=pc1 > 0,
        direction="spread across ordination space",
        caveats=[
            "Ordination summarises multidimensional structure — visual clusters should be confirmed with a statistical test (e.g. PERMANOVA).",
            *(["Subsampled dataset; full dataset may show different structure."] if sub else []),
        ],
        what_it_does_not_tell_you=[
            "This plot does not test whether groups are statistically different.",
            "Explained variance is specific to this distance metric and dataset.",
        ],
    )


def _facts_enrichment(result: dict) -> InterpretationFacts:
    n_sig = result.get("n_significant", 0)
    n_features = len(result.get("features", []))
    alpha = result.get("alpha", 0.05)
    correction = result.get("correction", "bh")
    groups = result.get("groups", [])
    sig_features = result.get("significant_features", [])
    n_a = result.get("n_group_a", 0)
    n_b = result.get("n_group_b", 0)

    return InterpretationFacts(
        method_id="fisher_exact",
        n_samples=n_a + n_b,
        result_summary=(
            f"{n_sig} of {n_features} BGC classes significantly enriched between "
            f"{groups[0] if groups else 'group A'} (n={n_a}) and "
            f"{groups[1] if len(groups) > 1 else 'group B'} (n={n_b}) "
            f"(Fisher's exact, adj. α={alpha}, {correction.upper()} correction)."
        ),
        key_numbers={
            "n_significant": float(n_sig),
            "n_tested": float(n_features),
            "alpha": alpha,
            "n_group_a": float(n_a),
            "n_group_b": float(n_b),
        },
        significant=n_sig > 0,
        direction=f"enriched in one group" if n_sig > 0 else "no enrichment detected",
        groups=groups,
        caveats=[
            f"Multiple-testing correction applied (BH FDR, α={alpha}); {n_features} hypotheses tested.",
            "Fisher's exact test assumes independence of BGC class presence across genomes.",
            f"Group sizes: {groups[0] if groups else 'A'}={n_a}, {groups[1] if len(groups) > 1 else 'B'}={n_b}."
            if groups else "Group sizes shown above.",
        ],
        what_it_does_not_tell_you=[
            "This test does not indicate why a BGC class is enriched — only that it is more frequent in one group.",
            "Enrichment does not imply functional difference without wet-lab validation.",
        ],
    )


def _facts_diversity(result: dict) -> InterpretationFacts:
    records = result.get("results", [])
    metrics = result.get("metrics", ["shannon"])
    n = result.get("n_genomes", len(records))

    key_nums: dict[str, float] = {"n_genomes": float(n)}
    summaries = []
    for metric in metrics:
        vals = [r.get(metric) for r in records if r.get(metric) is not None]
        if vals:
            mean_val = sum(vals) / len(vals)
            key_nums[f"mean_{metric}"] = round(mean_val, 4)
            summaries.append(f"mean {metric.capitalize()} = {mean_val:.2f}")

    return InterpretationFacts(
        method_id="alpha_diversity",
        n_samples=n,
        result_summary=f"Alpha diversity for {n} genomes: {'; '.join(summaries)}.",
        key_numbers=key_nums,
        significant=True,
        direction="variable across genomes",
        caveats=[
            "Alpha diversity is calculated per genome from BGC class counts — not from sequence read depth.",
            "Comparisons across groups require a statistical test (e.g. Kruskal-Wallis).",
        ],
        what_it_does_not_tell_you=[
            "High diversity does not imply ecological or functional superiority.",
            "Shannon index is sensitive to rare BGC classes; Simpson index weights common classes more.",
        ],
    )


def _facts_clustering(result: dict) -> InterpretationFacts:
    n = result.get("n_genomes", 0)
    n_clusters = result.get("n_clusters_requested")
    linkage = result.get("linkage", "ward")

    return InterpretationFacts(
        method_id="hierarchical_clustering",
        n_samples=n,
        result_summary=(
            f"Hierarchical clustering ({linkage} linkage) of {n} genomes"
            + (f" cut into {n_clusters} clusters." if n_clusters else " — dendrogram shown.")
        ),
        key_numbers={"n_genomes": float(n), "n_clusters": float(n_clusters or 0)},
        significant=True,
        direction="grouped by BGC profile similarity",
        caveats=[
            "Cluster boundaries depend on the linkage method and distance metric chosen.",
            "The optimal number of clusters is not determined automatically.",
        ],
        what_it_does_not_tell_you=[
            "Clustering does not test statistical significance of group differences.",
            "Genome proximity in the dendrogram reflects BGC profile similarity, not phylogenetic distance.",
        ],
    )


def _facts_community(result: dict) -> InterpretationFacts:
    n_comm = result.get("n_communities", 0)
    modularity = result.get("modularity", 0.0)
    n_nodes = result.get("n_nodes", 0)

    return InterpretationFacts(
        method_id="louvain_community",
        n_samples=n_nodes,
        result_summary=(
            f"Louvain community detection found {n_comm} communities among {n_nodes} GCFs "
            f"(modularity Q={modularity:.3f})."
        ),
        key_numbers={"n_communities": float(n_comm), "modularity": modularity, "n_nodes": float(n_nodes)},
        significant=modularity > 0.3,
        direction=f"{n_comm} distinct GCF communities detected",
        caveats=[
            "Modularity above 0.3 is generally considered meaningful community structure.",
            f"Louvain is non-deterministic; results may vary slightly between runs (seed fixed here).",
        ],
        what_it_does_not_tell_you=[
            "Communities reflect co-occurrence patterns in the network, not phylogenetic or functional groupings.",
            "The number of communities is determined by the algorithm, not pre-specified.",
        ],
    )


def _facts_permanova(result: dict) -> InterpretationFacts:
    p = result.get("pvalue", 1.0)
    f = result.get("test_statistic", 0.0)
    n = result.get("n_genomes", 0)
    groups = result.get("groups", [])
    perms = result.get("permutations", 999)

    return InterpretationFacts(
        method_id="permanova",
        n_samples=n,
        result_summary=(
            f"PERMANOVA: F={f:.4f}, p={p:.4f} ({perms} permutations), n={n} genomes."
        ),
        key_numbers={"f_statistic": f, "pvalue": p, "n_genomes": float(n), "permutations": float(perms)},
        significant=p <= 0.05,
        direction="groups significantly separated" if p <= 0.05 else "no significant group separation",
        groups=groups,
        caveats=[
            f"PERMANOVA p-value based on {perms} permutations — precision is 1/{perms}.",
            "PERMANOVA is sensitive to differences in group dispersion as well as group centroids.",
        ],
        what_it_does_not_tell_you=[
            "A significant PERMANOVA does not identify which specific BGC classes drive the separation.",
            "The test does not distinguish centroid differences from dispersion differences.",
        ],
    )


def _facts_generic(result: dict) -> InterpretationFacts:
    n = result.get("n_genomes", result.get("n_samples", 0))
    return InterpretationFacts(
        method_id=result.get("method", "unknown"),
        n_samples=n,
        result_summary=f"Analysis completed on {n} samples.",
        key_numbers={"n_samples": float(n)},
        significant=False,
        direction="see result object for details",
        caveats=["Interpretation template not available for this method."],
        what_it_does_not_tell_you=["See the method documentation for interpretation guidance."],
    )
