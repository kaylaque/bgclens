from bgclens.validation.harness import CheckResult


def check_has_r2_and_pvalue(result: dict) -> CheckResult:
    ok = "r2" in result and "pvalue" in result
    return CheckResult("has_r2_and_pvalue", ok)


def check_pvalue_in_range(result: dict) -> CheckResult:
    pval = result.get("pvalue", -1)
    ok = isinstance(pval, float) and 0.0 <= pval <= 1.0
    return CheckResult("pvalue_in_range", ok, f"pvalue={pval}")


def check_r2_in_range(result: dict) -> CheckResult:
    r2 = result.get("r2", -1)
    ok = isinstance(r2, float) and 0.0 <= r2 <= 1.0
    return CheckResult("r2_in_range", ok, f"r2={r2}")


VALIDATORS = [check_has_r2_and_pvalue, check_pvalue_in_range, check_r2_in_range]
