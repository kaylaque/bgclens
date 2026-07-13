"""Reduce a batch of RunRecord results to a TLDR biology summary."""
from __future__ import annotations
import logging
from bgclens.interpret.facts import InterpretationFacts

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a bioinformatics expert summarising BGC (biosynthetic gene cluster) analysis results.
Given a set of per-analysis results, write a short TLDR that a bench scientist can act on.

Your summary must:
- Lead with the most biologically meaningful finding
- Translate statistics into ecological/metabolic terms (what does it mean for secondary metabolism?)
- End with 1 sentence on the most promising next step

STRICT RULES:
1. Only use numbers that are explicitly provided in the input.
2. Do NOT fabricate PMIDs, DOIs, accession numbers, or database entries.
3. 3-5 sentences maximum.
4. Output only the TLDR text — no headers, no preamble, no bullet points.
"""


def reduce_summary(records: list) -> str:
    """Compose a TLDR biology narrative from a list of RunRecord or result dicts.

    Returns deterministic fallback if LLM unavailable or fails.
    Always safe to call — never raises.
    """
    try:
        if not records:
            return "No analysis results to summarise."

        snippets: list[str] = []
        all_key_numbers: dict[str, float] = {}

        for rec in records:
            if isinstance(rec, dict):
                cluster_id = rec.get("_cluster_id", "")
                method_id = rec.get("method", rec.get("_method_id", "unknown"))
                interp = rec.get("interpretation", "")
                n = rec.get("n_genomes", rec.get("n_samples", 0))

                # Build a rich snippet including interpretation text
                parts = [f"{method_id}"]
                if cluster_id:
                    parts.append(f"cluster {cluster_id}")
                if n:
                    parts.append(f"n={n} genomes")
                if interp:
                    # Trim to first 200 chars to avoid token overload
                    parts.append(f"— {interp[:200]}")
                elif "pvalue" in rec:
                    parts.append(f"p={rec['pvalue']:.4f}")
                    all_key_numbers[f"{method_id}_p"] = float(rec["pvalue"])
                if "n_significant" in rec:
                    parts.append(f"{rec['n_significant']} significant features")
                    all_key_numbers[f"{method_id}_n_sig"] = float(rec["n_significant"])
                snippets.append(". ".join(parts) + ".")
            else:
                # RunRecord object
                rs = getattr(rec, "result_summary", {}) or {}
                run_spec = getattr(rec, "run_spec", {}) or {}
                cid = run_spec.get("cluster_id", "")
                mid = run_spec.get("method_id", "analysis")
                interp = rs.get("interpretation", "")
                n = rs.get("n_genomes", 0)

                parts = [f"{mid}"]
                if cid:
                    parts.append(f"cluster {cid}")
                if n:
                    parts.append(f"n={n} genomes")
                if interp:
                    parts.append(f"— {interp[:200]}")
                snippets.append(". ".join(parts) + ".")

        input_text = "\n".join(f"- {s}" for s in snippets)
        n_analyses = len(records)
        fallback = (
            f"Completed {n_analyses} analysis{'es' if n_analyses != 1 else ''}. "
            "Review individual sections below for detailed results."
        )

        try:
            from bgclens.core.config import get_settings
            settings = get_settings()
            llm_cfg = settings.llm
            if not llm_cfg.enabled or not llm_cfg.api_key:
                return fallback

            from openai import OpenAI
            client = OpenAI(base_url=llm_cfg.base_url, api_key=llm_cfg.api_key)
            response = client.chat.completions.create(
                model=llm_cfg.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": (
                        f"Analysis results ({n_analyses} total):\n{input_text}\n\n"
                        "Write a 3-5 sentence TLDR biology summary a bench scientist can act on."
                    )},
                ],
                temperature=0.3,
                max_tokens=600,
            )
            msg = response.choices[0].message
            raw = (msg.content or "").strip()
            # Reasoning model fallback
            if not raw:
                rc = (getattr(msg, "reasoning_content", None) or "").strip()
                if rc:
                    raw = rc[-600:].strip()

            if not raw:
                return fallback

            # Guard: reject if response is suspiciously long or contains disallowed patterns
            import re
            if re.search(r'\b(PMID|DOI|doi\.org|uniprot\.org)\b', raw, re.IGNORECASE):
                return fallback

            return raw

        except Exception as e:
            logger.debug("reduce_summary LLM failed: %s", e)
            return fallback

    except Exception as e:
        logger.warning("reduce_summary failed: %s", e)
        return "Summary unavailable."
