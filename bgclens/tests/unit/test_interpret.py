"""Tests for the interpretation service."""
import pytest
from bgclens.interpret.facts import extract_facts, InterpretationFacts
from bgclens.interpret.templates import render_template
from bgclens.interpret.guard import validate as guard_validate


def _pcoa_result():
    return {
        "method": "pcoa",
        "genome_ids": ["g1", "g2", "g3"],
        "coordinates": [[0.1, 0.2], [-0.3, 0.1], [0.4, -0.2]],
        "explained_variance_pct": [42.5, 18.3],
        "n_genomes": 3,
        "subsampled": False,
    }


def _enrichment_result():
    return {
        "method": "fisher_exact",
        "features": ["terpene", "nrps"],
        "pvalues_adj": [0.01, 0.6],
        "odds_ratios": [3.1, 0.9],
        "significant_features": ["terpene"],
        "n_significant": 1,
        "alpha": 0.05,
        "correction": "bh",
        "groups": ["clade_A", "clade_B"],
        "n_group_a": 5,
        "n_group_b": 7,
    }


def test_extract_facts_pcoa():
    facts = extract_facts(_pcoa_result())
    assert facts.method_id == "pcoa"
    assert facts.n_samples == 3
    assert "42.5" in str(facts.key_numbers) or 42.5 in facts.key_numbers.values()
    assert len(facts.caveats) >= 1
    assert len(facts.what_it_does_not_tell_you) >= 1


def test_extract_facts_enrichment():
    facts = extract_facts(_enrichment_result())
    assert facts.method_id == "fisher_exact"
    assert facts.significant is True
    assert 1.0 in facts.key_numbers.values() or facts.key_numbers.get("n_significant") == 1.0


def test_render_template_contains_sections():
    facts = extract_facts(_pcoa_result())
    text = render_template(facts)
    assert "## Method" in text
    assert "## Result" in text
    assert "## Caveats" in text
    assert "## What this does NOT tell you" in text


def test_render_template_enrichment():
    facts = extract_facts(_enrichment_result())
    text = render_template(facts)
    assert "Fisher" in text
    assert "clade_A" in text or "group" in text.lower()


def test_guard_strips_fabricated_doi():
    facts = extract_facts(_pcoa_result())
    llm_text = "This is a real sentence. See Smith et al. 10.1234/fake.doi for details."
    result = guard_validate(llm_text, facts)
    assert "10.1234" not in result
    assert "This is a real sentence" in result


def test_guard_strips_fabricated_number():
    facts = extract_facts(_pcoa_result())
    # facts.key_numbers has n_genomes=3, pc1=42.5, pc2=18.3
    llm_text = "PC1 explains 42.5% of variance. A total of 9999 additional analyses confirm this."
    result = guard_validate(llm_text, facts)
    assert "9999" not in result
    # The 42.5 sentence should be kept
    assert "42.5" in result or "PC1" in result


def test_guard_allows_allowed_numbers():
    facts = extract_facts(_pcoa_result())
    # 42.5 and 18.3 are in key_numbers
    llm_text = "PC1 explains 42.5% and PC2 explains 18.3% of the variance in the dataset."
    result = guard_validate(llm_text, facts)
    assert "42.5" in result or "18.3" in result


def test_guard_strips_pmid():
    facts = extract_facts(_pcoa_result())
    text = "See PMID 12345678 for the original method."
    result = guard_validate(text, facts)
    assert "PMID" not in result


def test_interpret_pipeline_no_llm():
    from bgclens.interpret import interpret
    output = interpret(_pcoa_result(), use_llm=False)
    assert "final_text" in output
    assert "## Method" in output["final_text"]
    assert output["llm_used"] is False


def test_assumption_warnings_in_facts():
    facts = extract_facts(_pcoa_result(), assumption_warnings=["Only 3 genomes — results may be unstable."])
    assert any("3 genomes" in w or "unstable" in w for w in facts.assumption_warnings)
    assert any("3 genomes" in c or "unstable" in c for c in facts.caveats)
