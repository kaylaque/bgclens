"""Multi-turn retrieval-augmented chat for BGCLens.

LLM role: narration and discovery over retrieved deterministic data.
Never writes validity fields, never invents values absent from context.
guard.validate() applied to every reply.
"""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bgclens.model import Mention, Turn
    from bgclens.core.provenance import RunRecord
    from bgclens.model import Project

logger = logging.getLogger(__name__)

_MAX_HISTORY = 6  # turns kept in context
_MAX_CONTEXT_CHARS = 4000  # cap on assembled retrieval context

_SYSTEM_PROMPT = """You are BGCLens Assistant — a scientific assistant for a bioinformatics tool
that analyses biosynthetic gene clusters (BGCs) from BGCFlow projects.

You answer questions about BGC analysis results, cluster profiles, and methodology.

STRICT RULES:
1. Only answer based on the CONTEXT provided below. If the answer is not in the context, say so.
2. Do NOT fabricate numbers, statistics, UniProt IDs, PMIDs, accession numbers, or sequences.
3. Do NOT write confidence scores or validity assessments — those are in the deterministic results.
4. Keep answers concise (2-5 sentences for factual questions, slightly more for methodology).
5. If a @mention scopes the question to a specific cluster or section, focus on that context.
"""


def _assemble_context(
    project: "Project",
    records: list,
    mentions: list["Mention"],
) -> tuple[str, dict]:
    """Build deterministic context string from project manifest + mentions + records.

    Returns (context_text, key_numbers_for_guard).
    Never calls LLM.
    """
    parts: list[str] = []
    key_numbers: dict[str, float] = {}

    # Project manifest
    m = project.manifest
    parts.append(f"Project: {m.project_name}")
    parts.append(f"Pipelines: {', '.join(sorted(m.available_pipelines)) or 'none'}")
    if project.gcf_presence_absence:
        pa = project.gcf_presence_absence
        gcf_n = len(pa.rows)
        genome_n = len(pa.cols)
        parts.append(f"GCF matrix: {gcf_n} GCFs x {genome_n} genomes")
        key_numbers["gcf_count"] = float(gcf_n)
        key_numbers["genome_count"] = float(genome_n)

    # Mention-scoped context
    for mention in mentions:
        oid = mention.object_id
        otype = mention.object_type

        if otype == "cluster" and project.gcf_presence_absence:
            pa = project.gcf_presence_absence
            if oid in pa.rows:
                idx = pa.rows.index(oid)
                row_vals = pa.values[idx]
                n_present = sum(1 for v in row_vals if v > 0)
                parts.append(f"\n@{oid} (cluster): present in {n_present}/{len(pa.cols)} genomes")
                key_numbers[f"{oid}_n_present"] = float(n_present)

        elif otype == "method":
            # Surface the most recent result for this method
            for rec in reversed(records):
                rs = getattr(rec, "result_summary", rec if isinstance(rec, dict) else {})
                method = rs.get("method") or (getattr(rec, "run_spec", None) or {}).get("method_id")
                if method == oid:
                    interp = rs.get("interpretation", "")
                    if interp:
                        parts.append(f"\n@{oid} result: {interp[:500]}")
                    break

    # Recent run records (last 3)
    for rec in records[-3:]:
        if isinstance(rec, dict):
            cid = rec.get("_cluster_id", "")
            mid = rec.get("method", rec.get("_method_id", ""))
            n = rec.get("n_genomes", rec.get("n_samples", 0))
            parts.append(f"Run: {mid} on {cid}, n={n}")
            if isinstance(n, (int, float)):
                key_numbers[f"{mid}_n"] = float(n)
        else:
            rs = getattr(rec, "result_summary", {}) or {}
            run_spec = getattr(rec, "run_spec", {}) or {}
            mid = run_spec.get("method_id", "")
            if mid:
                parts.append(f"Run: {mid} — {rs.get('interpretation', '')[:200]}")

    context = "\n".join(parts)
    if len(context) > _MAX_CONTEXT_CHARS:
        context = context[:_MAX_CONTEXT_CHARS] + "\n[context truncated]"
    return context, key_numbers


def chat(
    project: "Project",
    records: list,
    history: list["Turn"],
    message: str,
    mentions: list["Mention"] | None = None,
) -> "Turn":
    """Single chat turn with retrieval-augmented context.

    Returns a Turn(role='assistant', content=...).
    Always returns a Turn — never raises.
    """
    from bgclens.model import Turn
    from bgclens.interpret.facts import InterpretationFacts
    from bgclens.interpret.guard import validate

    mentions = mentions or []
    fallback_content = "I can only answer questions grounded in the loaded project data. Please try a more specific question about the analysis results."

    try:
        context_text, key_numbers = _assemble_context(project, records, mentions)

        # Try LLM
        try:
            from bgclens.core.config import get_settings
            settings = get_settings()
            llm_cfg = settings.llm
            if not llm_cfg.enabled or not llm_cfg.api_key:
                return Turn(
                    role="assistant",
                    content=f"[LLM not configured] Context assembled:\n{context_text[:500]}",
                    mentions=[m.object_id for m in mentions],
                )

            from openai import OpenAI
            client = OpenAI(base_url=llm_cfg.base_url, api_key=llm_cfg.api_key)

            messages = [{"role": "system", "content": _SYSTEM_PROMPT + f"\n\nCONTEXT:\n{context_text}"}]

            # Add history (capped)
            for turn in history[-_MAX_HISTORY:]:
                messages.append({"role": turn.role, "content": turn.content})

            messages.append({"role": "user", "content": message})

            response = client.chat.completions.create(
                model=llm_cfg.model,
                messages=messages,
                temperature=0.3,
                max_tokens=400,
            )
            raw_reply = (response.choices[0].message.content or "").strip() or fallback_content

            # Guard — allow any numbers from context
            facts = InterpretationFacts(
                method_id="chat",
                n_samples=0,
                result_summary=context_text[:200],
                key_numbers=key_numbers,
                significant=False,
                direction="chat",
            )
            guarded = validate(raw_reply, facts)
            reply_content = guarded.strip() if guarded.strip() else fallback_content

        except Exception as e:
            logger.debug("chat LLM call failed: %s", e)
            reply_content = fallback_content

        return Turn(
            role="assistant",
            content=reply_content,
            mentions=[m.object_id for m in mentions],
        )

    except Exception as e:
        logger.warning("chat() failed: %s", e)
        return Turn(role="assistant", content=fallback_content)
