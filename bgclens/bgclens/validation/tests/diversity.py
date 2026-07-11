from bgclens.validation.harness import CheckResult


def _scores(result: dict) -> list[float]:
    """Numeric diversity scores from either the legacy `diversity_scores` mapping
    or the real method output `results` (a list of per-genome dicts)."""
    if "diversity_scores" in result:
        s = result["diversity_scores"]
        vals = list(s.values()) if isinstance(s, dict) else list(s)
        return [v for v in vals if isinstance(v, (int, float))]
    rows = result.get("results")
    if isinstance(rows, list):
        vals: list[float] = []
        for r in rows:
            if isinstance(r, dict):
                vals += [v for k, v in r.items() if isinstance(v, (int, float))]
        return vals
    return []


def check_has_diversity_scores(result: dict) -> CheckResult:
    ok = len(_scores(result)) > 0
    return CheckResult("has_diversity_scores", ok)


def check_scores_non_negative(result: dict) -> CheckResult:
    vals = _scores(result)
    ok = all(v >= 0 for v in vals)
    return CheckResult("scores_non_negative", ok)


VALIDATORS = [check_has_diversity_scores, check_scores_non_negative]
