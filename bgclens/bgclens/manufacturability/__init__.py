"""Manufacturability package — Tier-A feature extraction and objective weight profile."""
from bgclens.manufacturability.features import compute_features, TierAFeatures
from bgclens.manufacturability.profile import (
    compute_profile,
    ManufacturabilityProfile,
    reorder_for_manufacturability,
    chassis_hint,
    blocker_flags,
)

__all__ = [
    "compute_features",
    "TierAFeatures",
    "compute_profile",
    "ManufacturabilityProfile",
    "reorder_for_manufacturability",
    "chassis_hint",
    "blocker_flags",
]
