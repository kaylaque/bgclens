"""Stage 3: OpenAI-compatible LLM phrasing of template prose (constrained).

The model actually deployed here is small and weak, not a frontier model, so
this endpoint is built as a harness rather than a single call: each step below
is a small function with one job, `goals.HARD_GOALS` states exactly what a
candidate must satisfy to be accepted, and a failed first attempt gets one
retry with a stricter prompt before falling back to the deterministic
template. See `bgclens.interpret.goals` for the goal definitions and
`bgclens.interpret.judge` for the (advisory, LLM-graded) soft goals.
"""
from __future__ import annotations
import re
from bgclens.interpret.facts import InterpretationFacts
from bgclens.interpret.guard import validate as guard_validate
from bgclens.interpret.goals import HARD_GOALS


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

_STRICT_SYSTEM_PROMPT = """You are a scientific writing assistant for a bioinformatics tool.
Your previous rephrasing broke one of the rules below. Try again, more carefully.

STRICT RULES (read carefully, follow exactly):
1. Do NOT add any numbers, statistics, or values that are not already in the provided text.
2. Do NOT add citations, DOIs, PMIDs, or database accession numbers.
3. Do NOT introduce any new scientific claims.
4. Reproduce every "##" section header from the input VERBATIM, in the same order.
5. Do NOT shorten or drop any caveat or "what this does not tell you" bullet.
6. Do NOT write any preamble, explanation, or code fence. Output ONLY the rephrased
   text itself — your reply must start directly with the first "##" header.
"""


def _build_client(cfg):
    """Construct the OpenAI-compatible client for the configured endpoint (lazy import)."""
    from openai import OpenAI
    return OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)


def build_messages(
    template_text: str,
    facts: InterpretationFacts,
    strict: bool = False,
) -> list[dict[str, str]]:
    """Build the chat messages for one rephrasing attempt.

    `strict=True` is used on retry: it restates the rules more forcefully and
    lists the exact headers that must be reproduced verbatim — the extra
    scaffolding a weak model needs when a lighter prompt wasn't enough.
    """
    system_prompt = _STRICT_SYSTEM_PROMPT if strict else _SYSTEM_PROMPT
    user_lines = [
        "Rephrase the following scientific interpretation for fluency.",
        f"Allowed numbers: {list(facts.key_numbers.values())}.",
    ]
    if strict:
        headers = [line.strip() for line in template_text.splitlines() if line.strip().startswith("##")]
        if headers:
            user_lines.append(f"Headers you must reproduce verbatim, in order: {headers}.")
    user_lines.append("")
    user_lines.append(template_text)

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n".join(user_lines)},
    ]


def call_chat(client, model: str, messages: list[dict[str, str]]) -> str:
    """Perform one chat completion against the configured endpoint; return raw text."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
        max_tokens=1200,
    )
    return response.choices[0].message.content or ""


_PREAMBLE_LEAD_RE = re.compile(
    r"^(here'?s|here is|sure[,!]?|certainly|of course|below is|"
    r"i'?ve rephrased|rephrased (version|text))\b",
    re.IGNORECASE,
)


def strip_artifacts(raw: str) -> str:
    """Remove leading meta-preamble lines and code fences a weak model tends to emit."""
    text = raw.strip()

    # Drop leading preamble lines (e.g. "Here's the rephrased text:") that
    # precede the real content, but never eat into an actual section header.
    lines = text.splitlines()
    while lines and not lines[0].strip().startswith("##") and _PREAMBLE_LEAD_RE.match(lines[0].strip()):
        lines.pop(0)
    text = "\n".join(lines).strip()

    if text.startswith("```"):
        lines = text.splitlines()
        # Drop the opening fence (optionally with a language tag) and, if present,
        # the matching closing fence.
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return text


def accepts(
    candidate: str,
    template_text: str,
    facts: InterpretationFacts,
) -> tuple[bool, list[str]]:
    """Run every hard goal against candidate; return (all_passed, failed_goal_ids)."""
    failed = [goal.id for goal in HARD_GOALS if not goal.check(candidate, template_text, facts)]
    return (not failed, failed)


def _attempt(client, model: str, template_text: str, facts: InterpretationFacts, strict: bool) -> str:
    messages = build_messages(template_text, facts, strict=strict)
    raw = call_chat(client, model, messages)
    cleaned = strip_artifacts(raw) or template_text
    return guard_validate(cleaned, facts)


def rephrase(
    template_text: str,
    facts: InterpretationFacts,
    model: str | None = None,
) -> str:
    """
    Call the configured OpenAI-compatible endpoint to rephrase template_text.

    A candidate must satisfy every goal in `goals.HARD_GOALS` to be accepted.
    A first candidate that fails gets one retry with a stricter prompt; if
    that also fails, or the endpoint is unavailable/disabled/erroring for any
    reason, this always falls back to template_text unchanged.
    """
    try:
        from bgclens.core.config import get_settings
        settings = get_settings()
        llm_cfg = settings.llm

        if not llm_cfg.enabled or not llm_cfg.api_key:
            return template_text

        client = _build_client(llm_cfg)
        chosen_model = model or llm_cfg.model

        candidate = _attempt(client, chosen_model, template_text, facts, strict=False)
        ok, _failed = accepts(candidate, template_text, facts)

        if not ok:
            candidate = _attempt(client, chosen_model, template_text, facts, strict=True)
            ok, _failed = accepts(candidate, template_text, facts)

        return candidate if ok else template_text

    except Exception:
        return template_text  # always fall back to template
