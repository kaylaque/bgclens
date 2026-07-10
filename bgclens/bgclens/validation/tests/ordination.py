from bgclens.validation.harness import CheckResult


def check_has_coordinates(result: dict) -> CheckResult:
    ok = "coordinates" in result and len(result["coordinates"]) > 0
    return CheckResult("has_coordinates", ok, "" if ok else "no coordinates in result")


def check_explained_variance_sums_to_one(result: dict) -> CheckResult:
    ev = result.get("explained_variance_ratio", [])
    if not ev:
        return CheckResult("explained_variance_present", False, "no explained_variance_ratio")
    total = sum(ev)
    ok = 0.99 <= total <= 1.01
    return CheckResult("explained_variance_sums_to_one", ok, f"sum={total:.3f}")


def check_n_components_matches(result: dict) -> CheckResult:
    coords = result.get("coordinates", [])
    ev = result.get("explained_variance_ratio", [])
    if not coords or not ev:
        return CheckResult("n_components_consistent", False, "missing data")
    n_expected = len(ev)
    ok = all(len(row) == n_expected for row in coords[:5])
    return CheckResult("n_components_consistent", ok, f"expected {n_expected} dims")


VALIDATORS = [check_has_coordinates, check_explained_variance_sums_to_one, check_n_components_matches]
