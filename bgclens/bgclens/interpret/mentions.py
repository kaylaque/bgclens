"""Parse and resolve @mention references in chat messages."""
from __future__ import annotations
import re
from bgclens.model import Mention


_MENTION_RE = re.compile(r"@([\w\-\.]+)")

# Object types recognized in the Knowledge Base
_CLUSTER_PREFIX = ("gcf_", "bgc_", "cluster_")
_METHOD_IDS = {
    "alpha_diversity", "pcoa", "pca", "fisher_exact",
    "hierarchical_clustering", "louvain_community", "permanova",
    "manufacturability",
}
_REPORT_PREFIX = ("analysis_", "section_", "summary", "cross_cluster", "manufacturability")


def _classify(object_id: str) -> str:
    lower = object_id.lower()
    if any(lower.startswith(p) for p in _CLUSTER_PREFIX):
        return "cluster"
    if lower in _METHOD_IDS:
        return "method"
    if any(lower.startswith(p) for p in _REPORT_PREFIX):
        return "report_section"
    return "dataset"


def parse(message: str, whitelist: set[str] | None = None) -> list[Mention]:
    """Extract @mentions from message and resolve against optional whitelist.

    Unknown mentions (not in whitelist, if provided) are dropped — never fabricated.
    """
    found: list[Mention] = []
    for m in _MENTION_RE.finditer(message):
        raw = m.group(0)
        object_id = m.group(1)
        if whitelist is not None and object_id not in whitelist:
            continue
        found.append(Mention(
            raw=raw,
            object_id=object_id,
            object_type=_classify(object_id),
        ))
    return found
