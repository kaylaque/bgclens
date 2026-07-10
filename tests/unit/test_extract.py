"""Unit tests for bgclens.literature.extract — ALL offline, no LLM calls."""
import json
import pytest
from unittest.mock import patch, MagicMock

from bgclens.literature.extract import (
    FieldEvidence,
    PaperExtract,
    extract_paper,
    _guard_evidence_spans,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ABSTRACT = (
    "We applied PCoA to visualise beta-diversity and used PERMANOVA to test "
    "significance. Samples came from Reticulitermes flavipes gut microbiomes."
)


def _make_field_evidence(method_term: str, evidence_span: str, confidence: float = 0.9) -> FieldEvidence:
    return FieldEvidence(method_term=method_term, evidence_span=evidence_span, confidence=confidence)


# ---------------------------------------------------------------------------
# Guard tests (no LLM involved)
# ---------------------------------------------------------------------------


def test_evidence_span_guard_removes_fabricated():
    """Guard keeps verbatim spans and removes fabricated ones."""
    valid_fe = _make_field_evidence("PCoA", "PCoA to visualise beta-diversity")
    fabricated_fe = _make_field_evidence("PERMANOVA", "this sentence does not exist in the abstract")

    extract = PaperExtract(
        source_text=ABSTRACT,
        method_mentions=[valid_fe, fabricated_fe],
    )
    result = _guard_evidence_spans(extract)

    assert len(result.method_mentions) == 1
    assert result.method_mentions[0].method_term == "PCoA"


def test_evidence_span_guard_empty_span():
    """Guard removes FieldEvidence with an empty evidence_span."""
    empty_fe = _make_field_evidence("PCoA", "")
    valid_fe = _make_field_evidence("PERMANOVA", "used PERMANOVA to test")

    extract = PaperExtract(
        source_text=ABSTRACT,
        method_mentions=[empty_fe, valid_fe],
    )
    result = _guard_evidence_spans(extract)

    assert len(result.method_mentions) == 1
    assert result.method_mentions[0].method_term == "PERMANOVA"


# ---------------------------------------------------------------------------
# extract_paper — LLM disabled / error paths
# ---------------------------------------------------------------------------


def _disabled_settings():
    cfg = MagicMock()
    cfg.llm.enabled = False
    cfg.llm.api_key = ""
    cfg.llm.model = "test-model"
    return cfg


def _enabled_settings():
    cfg = MagicMock()
    cfg.llm.enabled = True
    cfg.llm.api_key = "sk-test"
    cfg.llm.model = "test-model"
    cfg.llm.base_url = "https://api.example.com/v1"
    return cfg


def test_extract_paper_llm_disabled():
    """When LLM is disabled, returns failed=True without any HTTP call."""
    with patch("bgclens.literature.extract.get_settings", return_value=_disabled_settings()):  # noqa: SIM117
        result = extract_paper(ABSTRACT, ["PCoA", "PERMANOVA"])

    assert result.failed is True
    assert result.note == "LLM disabled"
    assert result.method_mentions == []
    assert result.organism_terms == []
    assert result.source_text == ABSTRACT


def test_extract_paper_llm_error():
    """When call_chat raises, returns failed=True with error note."""
    with (
        patch("bgclens.literature.extract.get_settings", return_value=_enabled_settings()),
        patch("bgclens.literature.extract._build_client", return_value=MagicMock()),
        patch("bgclens.literature.extract.call_chat", side_effect=RuntimeError("connection refused")),
    ):
        result = extract_paper(ABSTRACT, ["PCoA"])

    assert result.failed is True
    assert "LLM error" in result.note
    assert "connection refused" in result.note


# ---------------------------------------------------------------------------
# extract_paper — guard integration via stubbed call_chat
# ---------------------------------------------------------------------------


def _stub_call_chat_response(payload: dict):
    """Return a mock call_chat that returns the JSON-serialised payload."""
    return MagicMock(return_value=json.dumps(payload))


def test_extract_paper_all_fabricated_spans_removed():
    """If all LLM spans are fabricated, result has method_mentions=[] and failed=False."""
    payload = {
        "method_mentions": [
            {
                "method_term": "PCoA",
                "evidence_span": "this fabricated span is not in the abstract at all",
                "confidence": 0.9,
            }
        ],
        "organism_terms": ["Reticulitermes flavipes"],
    }
    with (
        patch("bgclens.literature.extract.get_settings", return_value=_enabled_settings()),
        patch("bgclens.literature.extract._build_client", return_value=MagicMock()),
        patch("bgclens.literature.extract.call_chat", _stub_call_chat_response(payload)),
    ):
        result = extract_paper(ABSTRACT, ["PCoA"])

    assert result.failed is False
    assert result.method_mentions == []
    assert "Reticulitermes flavipes" in result.organism_terms


def test_extract_paper_partial_valid_spans():
    """One valid + one fabricated span: only the valid one survives the guard."""
    payload = {
        "method_mentions": [
            {
                "method_term": "PCoA",
                "evidence_span": "PCoA to visualise beta-diversity",  # verbatim substring
                "confidence": 0.95,
            },
            {
                "method_term": "PERMANOVA",
                "evidence_span": "this is completely made up",  # not in abstract
                "confidence": 0.85,
            },
        ],
        "organism_terms": ["Reticulitermes flavipes"],
    }
    with (
        patch("bgclens.literature.extract.get_settings", return_value=_enabled_settings()),
        patch("bgclens.literature.extract._build_client", return_value=MagicMock()),
        patch("bgclens.literature.extract.call_chat", _stub_call_chat_response(payload)),
    ):
        result = extract_paper(ABSTRACT, ["PCoA", "PERMANOVA"])

    assert result.failed is False
    assert len(result.method_mentions) == 1
    assert result.method_mentions[0].method_term == "PCoA"
    assert result.method_mentions[0].evidence_span == "PCoA to visualise beta-diversity"
    assert result.method_mentions[0].confidence == pytest.approx(0.95)
