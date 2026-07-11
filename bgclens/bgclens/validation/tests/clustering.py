from bgclens.validation.harness import CheckResult


def _labels(result: dict) -> list:
    """Flat cluster labels from either the legacy `labels` key or the real
    method output `cluster_labels` (which is None until n_clusters is chosen)."""
    lab = result.get("labels")
    if lab is None:
        lab = result.get("cluster_labels")
    return lab if isinstance(lab, list) else []


def check_has_labels(result: dict) -> CheckResult:
    ok = len(_labels(result)) > 0
    return CheckResult("has_labels", ok)


def check_labels_are_ints(result: dict) -> CheckResult:
    labels = _labels(result)
    ok = all(isinstance(l, int) for l in labels)
    return CheckResult("labels_are_ints", ok)


VALIDATORS = [check_has_labels, check_labels_are_ints]
