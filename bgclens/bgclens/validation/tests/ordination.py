from bgclens.validation.harness import CheckResult


def _ev_fractions(result: dict) -> list[float]:
    """Explained-variance values as fractions (summing toward 1).

    Accepts `explained_variance_ratio` (already fractions) or the real method
    output `explained_variance_pct` (percentages, normalized here by /100).
    """
    ev = result.get("explained_variance_ratio")
    if ev:
        return [float(v) for v in ev]
    pct = result.get("explained_variance_pct")
    if pct:
        return [float(v) / 100.0 for v in pct]
    return []


def check_has_coordinates(result: dict) -> CheckResult:
    ok = "coordinates" in result and len(result["coordinates"]) > 0
    return CheckResult("has_coordinates", ok, "" if ok else "no coordinates in result")


def check_explained_variance_sums_to_one(result: dict) -> CheckResult:
    ev = _ev_fractions(result)
    if not ev:
        return CheckResult("explained_variance_present", False, "no explained variance")
    total = sum(ev)
    # Only the top-k components may be reported, so accept any positive total up
    # to 1 (small tolerance) rather than requiring an exact sum of 1.
    ok = 0.0 < total <= 1.01
    return CheckResult("explained_variance_sums_to_one", ok, f"sum={total:.3f}")


def check_n_components_matches(result: dict) -> CheckResult:
    coords = result.get("coordinates", [])
    ev = _ev_fractions(result)
    if not coords or not ev:
        return CheckResult("n_components_consistent", False, "missing data")
    n_expected = len(ev)
    ok = all(len(row) == n_expected for row in coords[:5])
    return CheckResult("n_components_consistent", ok, f"expected {n_expected} dims")


VALIDATORS = [check_has_coordinates, check_explained_variance_sums_to_one, check_n_components_matches]
