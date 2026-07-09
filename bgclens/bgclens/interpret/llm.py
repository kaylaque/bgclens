"""Stage 3: OpenAI-compatible LLM phrasing of template prose (constrained)."""
from __future__ import annotations
from bgclens.interpret.facts import InterpretationFacts
from bgclens.interpret.guard import validate as guard_validate


_SYSTEM_PROMPT = """You are a scientific writing assistant for a bioinformatics tool.
Your task is to rephrase a given interpretation text to be more fluent and readable.

STRICT RULES:
1. Do NOT add any numbers, statistics, or values that are not already in the provided text.
2. Do NOT add citations, DOIs, PMIDs, or database accession numbers.
3. Do NOT introduce any new scientific claims.
4. Keep all caveats and "what this does not tell you" sections intact.
5. Keep the same section headers (##).
6. Output ONLY the rephrased text — nothing else.
"""


def rephrase(
    template_text: str,
    facts: InterpretationFacts,
    model: str | None = None,
) -> str:
    """
    Call the configured OpenAI-compatible endpoint to rephrase template_text.
    Returns guarded output. Falls back to template_text if LLM is unavailable or disabled.
    """
    try:
        from bgclens.core.config import get_settings
        settings = get_settings()
        llm_cfg = settings.llm

        if not llm_cfg.enabled or not llm_cfg.api_key:
            return template_text

        from openai import OpenAI
        client = OpenAI(
            base_url=llm_cfg.base_url,
            api_key=llm_cfg.api_key,
        )
        chosen_model = model or llm_cfg.model

        response = client.chat.completions.create(
            model=chosen_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Rephrase the following scientific interpretation for fluency. "
                        f"Allowed numbers: {list(facts.key_numbers.values())}.\n\n"
                        f"{template_text}"
                    ),
                },
            ],
            temperature=0.3,
            max_tokens=1200,
        )
        raw = response.choices[0].message.content or template_text
        return guard_validate(raw, facts)

    except Exception:
        return template_text  # always fall back to template
