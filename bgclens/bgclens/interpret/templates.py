"""Stage 2: deterministic template → prose from InterpretationFacts."""
from bgclens.interpret.facts import InterpretationFacts

_METHOD_NAMES = {
    "pcoa": "Principal Coordinates Analysis (PCoA)",
    "pca": "Principal Component Analysis (PCA)",
    "fisher_exact": "Fisher's Exact Test",
    "alpha_diversity": "Alpha Diversity Analysis",
    "hierarchical_clustering": "Hierarchical Clustering",
    "louvain_community": "Louvain Community Detection",
    "permanova": "PERMANOVA",
}


def render_template(facts: InterpretationFacts) -> str:
    """Generate full plain-language interpretation from InterpretationFacts."""
    method_name = _METHOD_NAMES.get(facts.method_id, facts.method_id)
    lines = []

    # What was tested
    lines.append(f"## Method\n{method_name} was applied to {facts.n_samples} samples.")

    # Result in plain language
    lines.append(f"\n## Result\n{facts.result_summary}")

    # Direction / significance
    if facts.significant:
        lines.append(f"\n**The analysis found a meaningful signal:** {facts.direction}.")
    else:
        lines.append(f"\n**No statistically significant signal was detected** for this comparison.")

    # Key numbers
    if facts.key_numbers:
        nums = "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in facts.key_numbers.items())
        lines.append(f"\n**Key values:** {nums}.")

    # Caveats
    if facts.caveats:
        caveat_block = "\n".join(f"- {c}" for c in facts.caveats)
        lines.append(f"\n## Caveats\n{caveat_block}")

    # What this does NOT tell you
    if facts.what_it_does_not_tell_you:
        not_block = "\n".join(f"- {s}" for s in facts.what_it_does_not_tell_you)
        lines.append(f"\n## What this does NOT tell you\n{not_block}")

    return "\n".join(lines)
