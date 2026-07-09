"""Interpretation service for BGCLens."""
from bgclens.interpret.facts import InterpretationFacts, extract_facts
from bgclens.interpret.templates import render_template
from bgclens.interpret.guard import validate as guard_validate
from bgclens.interpret.llm import rephrase


def interpret(
    result: dict,
    assumption_warnings: list[str] | None = None,
    use_llm: bool = True,
) -> dict:
    """
    Full three-stage interpretation pipeline.
    Returns a dict with keys: facts, template_text, final_text, llm_used.
    """
    facts = extract_facts(result, assumption_warnings)
    template_text = render_template(facts)

    if use_llm:
        final_text = rephrase(template_text, facts)
        llm_used = final_text != template_text
    else:
        final_text = template_text
        llm_used = False

    return {
        "facts": facts,
        "template_text": template_text,
        "final_text": final_text,
        "llm_used": llm_used,
    }


__all__ = [
    "InterpretationFacts",
    "extract_facts",
    "render_template",
    "guard_validate",
    "rephrase",
    "interpret",
]
