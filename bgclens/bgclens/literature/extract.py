"""Literature extraction module: structured evidence extraction from paper abstracts.

Uses the configured LLM (via interpret/llm.py) to extract method mentions and
organism terms from an abstract. Every evidence_span is guaranteed to be a
verbatim substring of the source text — fabricated quotes are silently dropped.

Never raises: always returns a PaperExtract, possibly with failed=True.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field

from bgclens.core.config import get_settings
from bgclens.interpret.llm import _build_client, call_chat


@dataclass
class FieldEvidence:
    method_term: str       # e.g. "PCoA", "PERMANOVA", "Fisher's test"
    evidence_span: str     # verbatim quote from abstract supporting this method mention
    confidence: float      # 0.0–1.0 LLM confidence


@dataclass
class PaperExtract:
    source_text: str
    method_mentions: list[FieldEvidence] = field(default_factory=list)
    organism_terms: list[str] = field(default_factory=list)
    failed: bool = False
    note: str = ""


_SYSTEM_PROMPT = (
    "You are a scientific text extraction tool. "
    "Extract analysis methods mentioned in the abstract. Return JSON only, "
    "with no extra text, no markdown fences, and no explanation."
)

_USER_TEMPLATE = """\
Abstract: {abstract}

Candidate methods: {methods}

Return JSON with this exact schema:
{{
  "method_mentions": [
    {{"method_term": "<one of the candidate methods>",
      "evidence_span": "<verbatim quote from the abstract>",
      "confidence": <0.0-1.0>}}
  ],
  "organism_terms": ["<organism or environment name>"]
}}

Only include method_mentions for methods that actually appear in the abstract.
evidence_span MUST be copied verbatim from the abstract text."""


def _guard_evidence_spans(extract: PaperExtract) -> PaperExtract:
    """Remove FieldEvidence items whose evidence_span is not a verbatim substring of source_text."""
    valid = [
        fe for fe in extract.method_mentions
        if fe.evidence_span and fe.evidence_span in extract.source_text
    ]
    return dataclasses.replace(extract, method_mentions=valid)


def extract_paper(
    abstract_text: str,
    candidate_methods: list[str],
    model: str | None = None,
) -> PaperExtract:
    """Use the configured LLM to extract structured method evidence from abstract_text.

    Returns PaperExtract.failed=True if LLM is disabled, unavailable, or returns
    nothing usable. Every FieldEvidence.evidence_span in the result is guaranteed
    to be a verbatim substring of abstract_text.
    """
    try:
        settings = get_settings()
        llm_cfg = settings.llm

        if not llm_cfg.enabled or not llm_cfg.api_key:
            return PaperExtract(
                source_text=abstract_text,
                failed=True,
                note="LLM disabled",
            )

        client = _build_client(llm_cfg)
        chosen_model = model or llm_cfg.model

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _USER_TEMPLATE.format(
                    abstract=abstract_text,
                    methods=", ".join(candidate_methods),
                ),
            },
        ]

        raw = call_chat(client, chosen_model, messages)

    except Exception as exc:
        short = str(exc)[:120]
        return PaperExtract(
            source_text=abstract_text,
            failed=True,
            note=f"LLM error: {short}",
        )

    # Parse JSON response
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return PaperExtract(
            source_text=abstract_text,
            failed=True,
            note=f"LLM error: JSON parse failed — {exc}",
        )

    if not isinstance(data, dict):
        return PaperExtract(
            source_text=abstract_text,
            failed=True,
            note="LLM error: unexpected response shape",
        )

    # Build typed result
    method_mentions: list[FieldEvidence] = []
    for item in data.get("method_mentions", []):
        try:
            method_mentions.append(
                FieldEvidence(
                    method_term=str(item.get("method_term", "")),
                    evidence_span=str(item.get("evidence_span", "")),
                    confidence=max(0.0, min(1.0, float(item.get("confidence", 0.0)))),
                )
            )
        except (TypeError, ValueError):
            continue  # skip malformed entries

    organism_terms: list[str] = [str(t) for t in (data.get("organism_terms") or [])]

    extract = PaperExtract(
        source_text=abstract_text,
        method_mentions=method_mentions,
        organism_terms=organism_terms,
        failed=False,
        note="",
    )

    return _guard_evidence_spans(extract)
