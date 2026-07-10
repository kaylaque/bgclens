from bgclens.validation.harness import CheckResult


def check_has_diversity_scores(result: dict) -> CheckResult:
    ok = "diversity_scores" in result and len(result["diversity_scores"]) > 0
    return CheckResult("has_diversity_scores", ok)


def check_scores_non_negative(result: dict) -> CheckResult:
    scores = result.get("diversity_scores", {})
    vals = list(scores.values()) if isinstance(scores, dict) else scores
    ok = all(v >= 0 for v in vals if isinstance(v, (int, float)))
    return CheckResult("scores_non_negative", ok)


VALIDATORS = [check_has_diversity_scores, check_scores_non_negative]
