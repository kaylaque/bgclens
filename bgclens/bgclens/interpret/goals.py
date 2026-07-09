"""Explicit goals of the LLM rephrasing endpoint.

Stage 3 (`bgclens.interpret.llm.rephrase`) is not "call an LLM and hope" — it is
held to a small set of named, individually-checkable goals. Hard goals are
deterministic and gate whether a candidate is accepted (see `llm.accepts`);
soft goals are advisory and are only ever graded by an LLM judge
(`bgclens.interpret.judge`), never used to gate.

The model actually deployed against this endpoint is a small, weak model (not
a frontier model), so goals are kept binary and mechanical wherever possible —
that is what a weak model, and a weak judge, can reliably be checked against.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Callable
from bgclens.interpret.facts import InterpretationFacts
from bgclens.interpret.guard import has_violations

_HEADER_RE = re.compile(r"^##\s+.+$", re.MULTILINE)

_PREAMBLE_RE = re.compile(
    r"^\s*(```|here'?s|here is|sure[,!]|certainly|of course|below is|"
    r"i'?ve rephrased|rephrased (version|text)|as an ai)",
    re.IGNORECASE,
)

# A candidate this much shorter than the template has likely dropped content
# rather than merely tightened the prose.
MIN_LENGTH_RATIO = 0.6


def _extract_headers(text: str) -> list[str]:
    return [line.strip() for line in _HEADER_RE.findall(text)]


def check_fidelity(candidate: str, template_text: str, facts: InterpretationFacts) -> bool:
    """G1 fidelity: introduces no number/DOI/PMID/accession absent from the facts."""
    return not has_violations(candidate, facts)


def check_structure(candidate: str, template_text: str, facts: InterpretationFacts) -> bool:
    """G2 structure: every '##' header in the template survives in the candidate."""
    template_headers = _extract_headers(template_text)
    if not template_headers:
        return True
    return all(header in candidate for header in template_headers)


def check_no_preamble(candidate: str, template_text: str, facts: InterpretationFacts) -> bool:
    """G3 no-preamble: candidate does not open with meta-commentary or a code fence."""
    stripped = candidate.strip()
    if not stripped:
        return False
    return _PREAMBLE_RE.match(stripped) is None


def check_substance(candidate: str, template_text: str, facts: InterpretationFacts) -> bool:
    """G4 substance: candidate is non-empty and not drastically shorter than the template."""
    stripped = candidate.strip()
    if not stripped:
        return False
    if not template_text.strip():
        return True
    return len(stripped) >= MIN_LENGTH_RATIO * len(template_text.strip())


@dataclass(frozen=True)
class Goal:
    id: str
    description: str
    check: Callable[[str, str, InterpretationFacts], bool] | None = None


# Hard goals: deterministic, gate acceptance of a candidate (see llm.accepts).
HARD_GOALS: list[Goal] = [
    Goal("fidelity", "Introduces no number/DOI/PMID/accession absent from the source facts.", check_fidelity),
    Goal("structure", "Every '##' section header from the template survives in the candidate.", check_structure),
    Goal("no_preamble", "Candidate does not open with meta-commentary or a code fence.", check_no_preamble),
    Goal("substance", "Candidate is non-empty and not drastically shorter than the template.", check_substance),
]

# Soft goals: advisory only, graded by an LLM judge, never gate the endpoint.
SOFT_GOALS: list[Goal] = [
    Goal("meaning_preserved", "Conveys the same findings as the template; adds no new scientific claim."),
    Goal("fluency_improved", "Reads at least as fluently as the template."),
]
