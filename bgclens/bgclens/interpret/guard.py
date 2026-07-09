"""Stage 3 guardrail: validate LLM output against InterpretationFacts."""
import re
from bgclens.interpret.facts import InterpretationFacts

_NUMBER_RE = re.compile(r"\b\d+\.?\d*\b")
_DOI_RE = re.compile(r"10\.\d{4,}/\S+", re.IGNORECASE)
_PMID_RE = re.compile(r"\bPMID\s*:?\s*\d+\b", re.IGNORECASE)
_ACCESSION_RE = re.compile(r"\b[A-Z]{1,3}\d{5,}\b")


def _allowed_numbers(facts: InterpretationFacts) -> set[str]:
    allowed_numbers = {str(int(v)) for v in facts.key_numbers.values() if v == int(v)}
    allowed_numbers |= {f"{v:.4f}" for v in facts.key_numbers.values()}
    allowed_numbers |= {f"{v:.2f}" for v in facts.key_numbers.values()}
    allowed_numbers |= {f"{v:.1f}" for v in facts.key_numbers.values()}
    allowed_numbers |= {str(v) for v in facts.key_numbers.values()}
    return allowed_numbers


def _sentence_violates(sentence: str, allowed_numbers: set[str]) -> bool:
    if _DOI_RE.search(sentence):
        return True  # fabricated DOI
    if _PMID_RE.search(sentence):
        return True  # fabricated PMID
    if _ACCESSION_RE.search(sentence):
        return True  # fabricated accession
    numbers_in_sentence = set(_NUMBER_RE.findall(sentence))
    # A sentence violates if it contains a number not in the allowed set
    return bool(numbers_in_sentence - allowed_numbers)


def has_violations(text: str, facts: InterpretationFacts) -> bool:
    """
    True if any sentence in text introduces a number, DOI, PMID, or accession
    not present in facts.key_numbers. Used by goal checks that need a yes/no
    verdict without discarding text (see bgclens.interpret.goals.check_fidelity).
    """
    allowed_numbers = _allowed_numbers(facts)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return any(_sentence_violates(sentence, allowed_numbers) for sentence in sentences)


def validate(llm_text: str, facts: InterpretationFacts) -> str:
    """
    Remove sentences from llm_text that introduce numbers, DOIs, PMIDs, or accessions
    not present in facts.key_numbers. Returns cleaned text.
    """
    allowed_numbers = _allowed_numbers(facts)
    sentences = re.split(r'(?<=[.!?])\s+', llm_text.strip())
    clean = [s for s in sentences if not _sentence_violates(s, allowed_numbers)]
    return " ".join(clean)
