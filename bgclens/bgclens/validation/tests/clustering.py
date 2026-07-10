from bgclens.validation.harness import CheckResult


def check_has_labels(result: dict) -> CheckResult:
    ok = "labels" in result and len(result["labels"]) > 0
    return CheckResult("has_labels", ok)


def check_labels_are_ints(result: dict) -> CheckResult:
    labels = result.get("labels", [])
    ok = all(isinstance(l, int) for l in labels)
    return CheckResult("labels_are_ints", ok)


VALIDATORS = [check_has_labels, check_labels_are_ints]
