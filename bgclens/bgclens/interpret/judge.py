"""LLM-as-judge grading of the soft goals in `bgclens.interpret.goals.SOFT_GOALS`.

Soft goals (meaning preserved, fluency improved) can't be checked
deterministically, so they're graded by asking the configured LLM simple
YES/NO questions — one line per goal. Binary questions are what a weak judge
model can answer reliably; free-form scoring is not. This module is
evaluation tooling only: it never gates `llm.rephrase`, and it fails open
(returns `{}`) on any error so a flaky or unconfigured judge never breaks a
run or a test.
"""
from __future__ import annotations
import re
from bgclens.interpret.facts import InterpretationFacts
from bgclens.interpret.goals import SOFT_GOALS
from bgclens.interpret.llm import _build_client, call_chat

_JUDGE_SYSTEM_PROMPT = """You are grading whether a rewritten scientific text meets
some criteria compared to the original text. For EACH numbered criterion below,
answer on its own line in the exact format:

<criterion_id>: YES
or
<criterion_id>: NO

Do not explain your answer. Do not add any other text."""


def _build_judge_prompt(template_text: str, final_text: str) -> str:
    criteria_lines = [f"{goal.id}: {goal.description}" for goal in SOFT_GOALS]
    return (
        "ORIGINAL TEXT:\n"
        f"{template_text}\n\n"
        "REWRITTEN TEXT:\n"
        f"{final_text}\n\n"
        "CRITERIA:\n" + "\n".join(criteria_lines)
    )


def _parse_verdicts(raw: str) -> dict[str, bool]:
    verdicts: dict[str, bool] = {}
    for goal in SOFT_GOALS:
        match = re.search(rf"\b{re.escape(goal.id)}\b\s*[:\-]?\s*(YES|NO)", raw, re.IGNORECASE)
        if match:
            verdicts[goal.id] = match.group(1).upper() == "YES"
    return verdicts


def judge_goals(
    template_text: str,
    final_text: str,
    facts: InterpretationFacts,
    model: str | None = None,
) -> dict[str, bool]:
    """
    Ask the configured LLM to grade final_text against SOFT_GOALS relative to
    template_text. Returns {goal_id: True/False} for every goal the judge
    answered; a goal missing from the result means the judge's reply couldn't
    be parsed for it. Returns {} on any error (unconfigured, unreachable,
    disabled) — this is evaluation tooling, not a gate.
    """
    try:
        from bgclens.core.config import get_settings
        settings = get_settings()
        llm_cfg = settings.llm

        if not llm_cfg.enabled or not llm_cfg.api_key:
            return {}

        client = _build_client(llm_cfg)
        chosen_model = model or llm_cfg.model

        messages = [
            {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": _build_judge_prompt(template_text, final_text)},
        ]
        raw = call_chat(client, chosen_model, messages)
        return _parse_verdicts(raw)

    except Exception:
        return {}
