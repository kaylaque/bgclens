from bgclens.validation.harness import CheckResult


def check_has_pvalues(result: dict) -> CheckResult:
    ok = "pvalues" in result or "results" in result
    return CheckResult("has_pvalues", ok)


def check_pvalues_in_range(result: dict) -> CheckResult:
    pvals = result.get("pvalues", result.get("results", {}))
    if isinstance(pvals, dict):
        vals = list(pvals.values())
    elif isinstance(pvals, list):
        vals = [r.get("pvalue", r.get("p_adjusted", 1.0)) for r in pvals if isinstance(r, dict)]
    else:
        vals = []
    ok = all(0.0 <= v <= 1.0 for v in vals if isinstance(v, float))
    return CheckResult("pvalues_in_range", ok if vals else False, f"{len(vals)} p-values checked")


VALIDATORS = [check_has_pvalues, check_pvalues_in_range]
