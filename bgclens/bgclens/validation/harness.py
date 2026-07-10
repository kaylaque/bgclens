"""Validation harness: run principle + contract checks for a method result."""
from __future__ import annotations
from dataclasses import dataclass, field
from bgclens.validation.bands import ConfidenceBand, band


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ValidationResult:
    method_id: str
    checks: list[CheckResult] = field(default_factory=list)
    confidence_band: ConfidenceBand = "amber"

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def total(self) -> int:
        return len(self.checks)


def evaluate(method_id: str, result: dict) -> ValidationResult:
    """Run validation checks for a method's output dict.

    Returns ValidationResult with banded confidence.
    Always returns a result — never raises.
    """
    from bgclens.validation import _METHOD_VALIDATORS

    validators = _METHOD_VALIDATORS.get(method_id, [])
    checks: list[CheckResult] = []

    for check_fn in validators:
        try:
            check_result = check_fn(result)
            checks.append(check_result)
        except Exception as exc:
            checks.append(CheckResult(
                name=getattr(check_fn, "__name__", "unknown"),
                passed=False,
                detail=f"check raised: {exc}",
            ))

    vr = ValidationResult(method_id=method_id, checks=checks)
    vr.confidence_band = band(vr.passed, vr.total)
    return vr
