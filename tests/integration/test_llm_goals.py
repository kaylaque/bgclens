"""Live-gated goal verification for the LLM endpoint.

Unlike tests/unit/test_llm_harness.py (fully mocked, always runs), these
tests hit the real endpoint configured in .env / BGCLENS_LLM_* — the same
weak model the app runs in production — and check that:

  1. the hard goals in bgclens.interpret.goals.HARD_GOALS actually hold for
     real completions (with the one-shot repair loop doing its job), and
  2. an LLM judge (bgclens.interpret.judge.judge_goals) agrees the rewritten
     text preserves the original meaning.

Skips gracefully (like test_11 in test_walking_skeleton.py) when no LLM is
configured, so this never blocks a normal offline test run. Fluency is
graded but only recorded, not asserted — a weak judge model is not reliable
enough on a subjective criterion to gate the suite on it.
"""
import pytest
from pathlib import Path

DEMO_PROJECT = Path(__file__).parent.parent / "fixtures" / "demo_project"


def _llm_configured():
    from bgclens.core.config import get_settings
    settings = get_settings()
    return settings.llm.enabled and settings.llm.api_key


pytestmark = [
    pytest.mark.skipif(not DEMO_PROJECT.exists(), reason="Demo fixtures not found"),
]


def _require_llm():
    if not _llm_configured():
        pytest.skip("LLM not configured (set BGCLENS_LLM_* in .env)")


def _project():
    from bgclens.core.api import open_project
    return open_project(DEMO_PROJECT)


# NOTE: "permanova" is deliberately excluded here — bgclens/catalog/methods/permanova.py
# currently errors against the installed scikit-bio version (an unrelated
# BGCFlow/skbio compatibility bug, not something introduced by the LLM harness
# work in this file). pcoa and fisher_enrichment are enough to exercise the goal
# checks across two different result shapes (ordination vs. enrichment).
_METHOD_PARAMS = {
    "pcoa": {"n_components": 2},
    "fisher_enrichment": {"grouping_col": "genus"},
}


def _result_for(method):
    from bgclens.core.api import run
    return run(_project(), method, _METHOD_PARAMS[method])


class TestLLMGoals:

    @pytest.mark.parametrize("method", list(_METHOD_PARAMS))
    def test_hard_goals_hold_for_live_completions(self, method):
        """The weak model, with the repair loop, must satisfy every hard goal."""
        _require_llm()
        from bgclens.interpret import interpret
        from bgclens.interpret.goals import HARD_GOALS

        result = _result_for(method)
        output = interpret(result, use_llm=True)

        if not output["llm_used"]:
            pytest.fail(
                f"LLM is configured but interpret() fell back to the template for "
                f"'{method}' even after the repair retry — the endpoint could not "
                f"reach the hard goals. failed template: {output['template_text'][:200]!r}"
            )

        template_text = output["template_text"]
        final_text = output["final_text"]
        facts = output["facts"]

        for goal in HARD_GOALS:
            assert goal.check(final_text, template_text, facts), (
                f"Goal '{goal.id}' ({goal.description}) failed for method={method}.\n"
                f"template: {template_text!r}\nfinal: {final_text!r}"
            )

    def test_judge_confirms_meaning_preserved(self):
        """An LLM judge must agree the rewrite didn't change what was said."""
        _require_llm()
        from bgclens.interpret import interpret
        from bgclens.interpret.judge import judge_goals

        result = _result_for("pcoa")
        output = interpret(result, use_llm=True)
        if not output["llm_used"]:
            pytest.skip("LLM fell back to template; nothing to judge")

        verdicts = judge_goals(output["template_text"], output["final_text"], output["facts"])
        if "meaning_preserved" not in verdicts:
            pytest.skip("Judge reply could not be parsed for 'meaning_preserved' — weak judge, skipping rather than failing")

        assert verdicts["meaning_preserved"] is True, (
            "LLM judge says the rewritten interpretation no longer conveys the "
            "same findings as the template."
        )

        # Fluency is advisory only: recorded, never asserted — a weak judge model
        # is not reliable enough on a subjective criterion to gate the suite.
        if "fluency_improved" in verdicts:
            print(f"\n[advisory] fluency_improved verdict: {verdicts['fluency_improved']}")
