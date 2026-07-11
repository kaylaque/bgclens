"""Unit tests for validation harness — all offline."""
from bgclens.validation import evaluate
from bgclens.validation.bands import band


def test_band_green():
    assert band(8, 10) == "green"


def test_band_amber_above_50():
    assert band(5, 10) == "amber"


def test_band_amber_below_50():
    assert band(4, 10) == "red"


def test_band_no_checks():
    assert band(0, 0) == "amber"


def test_evaluate_pcoa_green():
    result = {
        "coordinates": [[0.1, 0.2, 0.3]] * 8,
        "explained_variance_ratio": [0.5, 0.3, 0.2],
    }
    vr = evaluate("pcoa", result)
    assert vr.confidence_band == "green"
    assert vr.passed == vr.total


def test_evaluate_pcoa_red_empty_coords():
    result = {"coordinates": [], "explained_variance_ratio": []}
    vr = evaluate("pcoa", result)
    assert vr.confidence_band in ("amber", "red")
    assert vr.passed < vr.total


def test_evaluate_alpha_diversity_runs_checks():
    """Catalog method id 'alpha_diversity' must resolve validators (not default amber)."""
    result = {"diversity_scores": {"shannon": 2.1, "simpson": 0.8}}
    vr = evaluate("alpha_diversity", result)
    assert vr.total > 0
    assert vr.confidence_band == "green"
    assert vr.passed == vr.total


def test_evaluate_hierarchical_clustering_runs_checks():
    """Catalog method id 'hierarchical_clustering' must resolve validators (not default amber)."""
    result = {"labels": [0, 1, 0, 2]}
    vr = evaluate("hierarchical_clustering", result)
    assert vr.total > 0
    assert vr.confidence_band == "green"
    assert vr.passed == vr.total


def test_evaluate_unknown_method_returns_amber():
    vr = evaluate("nonexistent_method", {})
    assert vr.confidence_band == "amber"
    assert vr.total == 0


def test_evaluate_enrichment_pvalue_out_of_range():
    result = {"pvalues": {"BGC_type_A": 1.5}}
    vr = evaluate("fisher_enrichment", result)
    failing = [c for c in vr.checks if not c.passed]
    assert any("pvalue" in c.name for c in failing)


def test_evaluate_check_exception_does_not_propagate():
    """A check function that raises must not crash evaluate()."""
    from bgclens.validation import _METHOD_VALIDATORS

    def bad_check(result):
        raise RuntimeError("simulated check failure")

    _METHOD_VALIDATORS["_test_bad"] = [bad_check]
    try:
        vr = evaluate("_test_bad", {})
        assert vr.confidence_band in ("amber", "red")
        assert vr.checks[0].passed is False
        assert "check raised" in vr.checks[0].detail
    finally:
        del _METHOD_VALIDATORS["_test_bad"]
