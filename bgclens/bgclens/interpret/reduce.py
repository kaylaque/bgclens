"""Reduce a batch of RunRecord results to a single narrated summary.

The LLM role here is narration only: it reads the per-analysis outputs and
produces a cross-cluster story. It must not re-score or overwrite per-analysis
provenance. guard.validate() is applied before returning.
"""
from __future__ import annotations
import logging
from bgclens.interpret.facts import InterpretationFacts

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a scientific writing assistant for a bioinformatics tool called BGCLens.
You are given a set of per-cluster analysis results and must write a short cross-cluster narrative summary.

STRICT RULES:
1. Only narrate what the provided results say. Do NOT add numbers, scores, or values not in the input.
2. Do NOT write validity fields, confidence scores, or predictions.
3. Do NOT fabricate PMIDs, DOIs, accession numbers, or database entries.
4. Keep the summary to 3-5 sentences.
5. Output only the narrative — no headers, no preamble.
"""


def reduce_summary(records: list) -> str:
    """Compose a cross-cluster narrative from a list of RunRecord or result dicts.

    Returns deterministic fallback if LLM unavailable or fails guard check.
    Always safe to call — never raises.
    """
    try:
        if not records:
            return "No analysis results to summarise."

        # Build a compact text of what each analysis found
        snippets: list[str] = []
        all_key_numbers: dict[str, float] = {}
        for rec in records:
            if isinstance(rec, dict):
                cluster_id = rec.get("_cluster_id", "unknown")
                method_id = rec.get("method", rec.get("_method_id", "unknown"))
                n = rec.get("n_genomes", rec.get("n_samples", 0))
                snippet = f"Cluster {cluster_id} ({method_id}): n={n}."
                if "pvalue" in rec:
                    snippet += f" p={rec['pvalue']:.4f}."
                    all_key_numbers[f"{cluster_id}_p"] = float(rec["pvalue"])
                if "n_significant" in rec:
                    snippet += f" {rec['n_significant']} significant features."
                    all_key_numbers[f"{cluster_id}_n_sig"] = float(rec["n_significant"])
                snippets.append(snippet)
            else:
                # RunRecord object
                rs = getattr(rec, "result_summary", {}) or {}
                cid = (getattr(rec, "run_spec", None) or {}).get("cluster_id", "unknown")
                snippets.append(f"Cluster {cid}: {rs.get('interpretation', 'completed.')}")

        input_text = " ".join(snippets)
        fallback = f"Analysis completed across {len(records)} cluster-method pairs. " + input_text

        # Attempt LLM narration
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
                    {"role": "user", "content": f"Per-cluster results:\n{input_text}\n\nWrite a 3-5 sentence cross-cluster narrative."},
                ],
                temperature=0.3,
                max_tokens=300,
            )
            raw = (response.choices[0].message.content or "").strip()

            # Apply guard — use the collected key numbers as allowed set
            facts = InterpretationFacts(
                method_id="reduce_summary",
                n_samples=len(records),
                result_summary=input_text,
                key_numbers=all_key_numbers,
                significant=False,
                direction="cross-cluster",
            )
            from bgclens.interpret.guard import validate
            guarded = validate(raw, facts)
            return guarded if guarded.strip() else fallback

        except Exception as e:
            logger.debug("reduce_summary LLM failed: %s", e)
            return fallback

    except Exception as e:
        logger.warning("reduce_summary failed: %s", e)
        return "Summary unavailable."
