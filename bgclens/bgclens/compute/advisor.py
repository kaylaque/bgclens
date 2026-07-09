"""Compute advisor: classify methods as Safe/Heavy/Likely-to-fail and suggest alternatives."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from bgclens.compute.resources import ResourceProfile, probe
from bgclens.compute.cost_models import LIGHTER_ALTERNATIVES, trade_off_for

_HEADROOM = 0.7  # Use at most 70% of available RAM before upgrading class


@dataclass
class CostAssessment:
    method_id: str
    cost_class: str           # "Safe" | "Heavy" | "Likely-to-fail"
    estimated_mb: float
    reason: str
    alternatives: list[AlternativeRecommendation] = field(default_factory=list)
    resource_profile: ResourceProfile | None = None


@dataclass
class AlternativeRecommendation:
    method_id: str
    cost_class: str
    trade_off: str


def assess(
    method_id: str,
    inputs: dict[str, Any],
    params: dict[str, Any],
    resource_profile: ResourceProfile | None = None,
) -> CostAssessment:
    """
    Assess compute cost for a method on given inputs.
    Optionally override the method's own class based on available RAM.
    """
    # Lazy import to avoid circular dependency with catalog agents
    from bgclens.catalog.registry import get_impl

    _, _, cost_fn = get_impl(method_id)
    estimate = cost_fn(inputs, params)

    method_class = estimate.get("class", "Safe")
    estimated_mb = float(estimate.get("estimated_mb", 0))
    reason = estimate.get("reason", "")

    # Override upward if RAM probe says it won't fit
    if resource_profile is None:
        try:
            resource_profile = probe()
        except Exception:
            resource_profile = None

    if resource_profile is not None:
        budget_mb = resource_profile.ram_available_mb * _HEADROOM
        if estimated_mb > budget_mb and method_class == "Safe":
            method_class = "Heavy"
            reason += f" (exceeds {budget_mb:.0f} MB available RAM budget)"
        elif estimated_mb > resource_profile.ram_total_mb * 0.9 and method_class != "Likely-to-fail":
            method_class = "Likely-to-fail"
            reason += f" (exceeds 90% of total RAM {resource_profile.ram_total_mb:.0f} MB)"

    alternatives = _recommend_alternatives(method_id, method_class)

    return CostAssessment(
        method_id=method_id,
        cost_class=method_class,
        estimated_mb=estimated_mb,
        reason=reason,
        alternatives=alternatives,
        resource_profile=resource_profile,
    )


def _recommend_alternatives(method_id: str, cost_class: str) -> list[AlternativeRecommendation]:
    if cost_class == "Safe":
        return []
    recs = []
    for alt_id, _ in LIGHTER_ALTERNATIVES.get(method_id, []):
        try:
            recs.append(AlternativeRecommendation(
                method_id=alt_id,
                cost_class="Safe",  # alternatives are always listed as cheaper
                trade_off=trade_off_for(method_id, alt_id),
            ))
        except Exception:
            pass
    return recs
