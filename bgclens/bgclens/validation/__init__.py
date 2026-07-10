"""Validation package — deterministic principle+contract checks per catalog method."""
from bgclens.validation.harness import evaluate, ValidationResult, CheckResult
from bgclens.validation.bands import ConfidenceBand, band

__all__ = ["evaluate", "ValidationResult", "CheckResult", "ConfidenceBand", "band"]

from bgclens.validation.tests.ordination import VALIDATORS as _ORDINATION
from bgclens.validation.tests.diversity import VALIDATORS as _DIVERSITY
from bgclens.validation.tests.enrichment import VALIDATORS as _ENRICHMENT
from bgclens.validation.tests.clustering import VALIDATORS as _CLUSTERING
from bgclens.validation.tests.permanova import VALIDATORS as _PERMANOVA

_METHOD_VALIDATORS: dict[str, list] = {
    "pcoa": _ORDINATION,
    "pca": _ORDINATION,
    "diversity": _DIVERSITY,
    "fisher_enrichment": _ENRICHMENT,
    "clustering": _CLUSTERING,
    "louvain_community": _CLUSTERING,
    "permanova": _PERMANOVA,
}
