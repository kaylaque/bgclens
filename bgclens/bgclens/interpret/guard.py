"""Stage 3 guardrail: validate LLM output against InterpretationFacts."""
import re
from bgclens.interpret.facts import InterpretationFacts

_NUMBER_RE = re.compile(r"\b\d+\.?\d*\b")
_DOI_RE = re.compile(r"10\.\d{4,}/\S+", re.IGNORECASE)
_PMID_RE = re.compile(r"\bPMID\s*:?\s*\d+\b", re.IGNORECASE)
_ACCESSION_RE = re.compile(r"\b[A-Z]{1,3}\d{5,}\b")


def validate(llm_text: str, facts: InterpretationFacts) -> str:
    """
    Remove sentences from llm_text that introduce numbers, DOIs, PMIDs, or accessions
    not present in facts.key_numbers. Returns cleaned text.
    """
    allowed_numbers = {str(int(v)) for v in facts.key_numbers.values() if v == int(v)}
    allowed_numbers |= {f"{v:.4f}" for v in facts.key_numbers.values()}
    allowed_numbers |= {f"{v:.2f}" for v in facts.key_numbers.values()}
    allowed_numbers |= {f"{v:.1f}" for v in facts.key_numbers.values()}
    allowed_numbers |= {str(v) for v in facts.key_numbers.values()}

    sentences = re.split(r'(?<=[.!?])\s+', llm_text.strip())
    clean = []
    for sentence in sentences:
        if _DOI_RE.search(sentence):
            continue  # strip fabricated DOIs
        if _PMID_RE.search(sentence):
            continue  # strip fabricated PMIDs
        if _ACCESSION_RE.search(sentence):
            continue  # strip fabricated accessions
        numbers_in_sentence = set(_NUMBER_RE.findall(sentence))
        # Allow sentence if it contains no numbers, or if all numbers are in the allowed set
        foreign = numbers_in_sentence - allowed_numbers
        if foreign:
            continue
        clean.append(sentence)
    return " ".join(clean)
