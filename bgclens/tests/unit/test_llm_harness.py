"""Offline tests for the harnessed LLM endpoint (bgclens.interpret.llm/.goals).

Every test here runs without a network call: the `openai` module is replaced
with a fake whose `chat.completions.create()` returns canned strings, so we
can exercise the success, repair, and fallback paths deterministically —
including the "successful response" path that the pre-existing live-gated
test (test_11 in test_walking_skeleton.py) could only cover with a real
endpoint configured.
"""
import sys
from types import ModuleType

from bgclens.interpret.facts import extract_facts
from bgclens.interpret.templates import render_template
from bgclens.interpret import goals
from bgclens.interpret.llm import build_messages, strip_artifacts, accepts, rephrase


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _pcoa_result():
    return {
        "method": "pcoa",
        "genome_ids": ["g1", "g2", "g3"],
        "coordinates": [[0.1, 0.2], [-0.3, 0.1], [0.4, -0.2]],
        "explained_variance_pct": [42.5, 18.3],
        "n_genomes": 3,
        "subsampled": False,
    }


def _facts_and_template():
    facts = extract_facts(_pcoa_result())
    template_text = render_template(facts)
    return facts, template_text


def _good_candidate(template_text: str) -> str:
    """A candidate that satisfies every hard goal against `template_text`."""
    headers = [line.strip() for line in template_text.splitlines() if line.strip().startswith("##")]
    body = []
    for header in headers:
        body.append(header)
        body.append("This is a fluently rephrased version of that section, restating the same facts and caveats without adding anything new.")
    return "\n\n".join(body)


def _install_fake_openai(monkeypatch, responses):
    """Install a fake `openai` module; successive create() calls return
    successive entries of `responses` (the last entry repeats for extra calls).
    Returns the list of kwargs each call was made with, for assertions."""
    calls = []

    class _FakeMessage:
        def __init__(self, content):
            self.content = content

    class _FakeChoice:
        def __init__(self, content):
            self.message = _FakeMessage(content)

    class _FakeResponse:
        def __init__(self, content):
            self.choices = [_FakeChoice(content)]

    class _FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            idx = min(len(calls) - 1, len(responses) - 1)
            return _FakeResponse(responses[idx])

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self.chat = _FakeChat()

    fake_module = ModuleType("openai")
    fake_module.OpenAI = _FakeClient
    monkeypatch.setitem(sys.modules, "openai", fake_module)
    return calls


def _enable_llm(monkeypatch, model="weak-model"):
    import bgclens.core.config as config
    from bgclens.core.config import BGCLensSettings, LLMSettings

    settings = BGCLensSettings(llm=LLMSettings(enabled=True, api_key="sk-test", model=model))
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    return settings


# ---------------------------------------------------------------------------
# build_messages
# ---------------------------------------------------------------------------

def test_build_messages_embeds_allowed_numbers():
    facts, template_text = _facts_and_template()
    messages = build_messages(template_text, facts, strict=False)
    user_content = messages[-1]["content"]
    assert "42.5" in user_content
    assert "18.3" in user_content
    assert template_text in user_content


def test_build_messages_strict_lists_headers_verbatim():
    facts, template_text = _facts_and_template()
    messages = build_messages(template_text, facts, strict=True)
    user_content = messages[-1]["content"]
    assert "## Method" in user_content
    assert "## Caveats" in user_content
    assert "verbatim" in user_content.lower()


# ---------------------------------------------------------------------------
# strip_artifacts
# ---------------------------------------------------------------------------

def test_strip_artifacts_removes_preamble_line():
    raw = "Here's the rephrased text:\n## Method\nSome content."
    cleaned = strip_artifacts(raw)
    assert cleaned.startswith("## Method")
    assert "Here's" not in cleaned


def test_strip_artifacts_removes_code_fence():
    raw = "```\n## Method\nSome content.\n```"
    cleaned = strip_artifacts(raw)
    assert cleaned.startswith("## Method")
    assert "```" not in cleaned


def test_strip_artifacts_leaves_clean_text_untouched():
    raw = "## Method\nSome content."
    assert strip_artifacts(raw) == raw


# ---------------------------------------------------------------------------
# Hard goal checks (goals.py)
# ---------------------------------------------------------------------------

def test_check_fidelity_passes_on_allowed_numbers():
    facts, template_text = _facts_and_template()
    candidate = "PC1 explains 42.5% and PC2 explains 18.3% of the variance."
    assert goals.check_fidelity(candidate, template_text, facts) is True


def test_check_fidelity_fails_on_fabricated_number():
    facts, template_text = _facts_and_template()
    candidate = "A total of 9999 additional genomes were also analysed."
    assert goals.check_fidelity(candidate, template_text, facts) is False


def test_check_structure_passes_when_headers_survive():
    facts, template_text = _facts_and_template()
    candidate = _good_candidate(template_text)
    assert goals.check_structure(candidate, template_text, facts) is True


def test_check_structure_fails_on_dropped_header():
    facts, template_text = _facts_and_template()
    candidate = "## Method\nSome content, but no other sections at all."
    assert goals.check_structure(candidate, template_text, facts) is False


def test_check_no_preamble_passes_on_clean_start():
    facts, template_text = _facts_and_template()
    assert goals.check_no_preamble("## Method\nSome content.", template_text, facts) is True


def test_check_no_preamble_fails_on_meta_commentary():
    facts, template_text = _facts_and_template()
    candidate = "Here's the rephrased text:\n## Method\nSome content."
    assert goals.check_no_preamble(candidate, template_text, facts) is False


def test_check_substance_fails_on_collapsed_output():
    facts, template_text = _facts_and_template()
    assert goals.check_substance("Great analysis!", template_text, facts) is False


def test_check_substance_fails_on_empty_output():
    facts, template_text = _facts_and_template()
    assert goals.check_substance("   ", template_text, facts) is False


def test_check_substance_passes_on_comparable_length():
    facts, template_text = _facts_and_template()
    candidate = _good_candidate(template_text)
    assert goals.check_substance(candidate, template_text, facts) is True


# ---------------------------------------------------------------------------
# accepts()
# ---------------------------------------------------------------------------

def test_accepts_reports_all_failed_goal_ids():
    facts, template_text = _facts_and_template()
    bad_candidate = "Here's the rephrased text: 9999 new genomes were found."
    ok, failed = accepts(bad_candidate, template_text, facts)
    assert ok is False
    assert "fidelity" in failed
    assert "structure" in failed
    assert "no_preamble" in failed


def test_accepts_passes_good_candidate():
    facts, template_text = _facts_and_template()
    candidate = _good_candidate(template_text)
    ok, failed = accepts(candidate, template_text, facts)
    assert ok is True
    assert failed == []


# ---------------------------------------------------------------------------
# rephrase() orchestration: success / repair / fallback
# ---------------------------------------------------------------------------

def test_rephrase_success_path_accepts_first_good_candidate(monkeypatch):
    facts, template_text = _facts_and_template()
    good = _good_candidate(template_text)
    _enable_llm(monkeypatch)
    calls = _install_fake_openai(monkeypatch, [good])

    result = rephrase(template_text, facts)

    assert result != template_text
    assert len(calls) == 1  # no retry needed


def test_rephrase_repair_path_retries_once_then_succeeds(monkeypatch):
    facts, template_text = _facts_and_template()
    bad = "Here's the rephrased text:\n9999 new genomes were found. This text is missing all the required sections."
    good = _good_candidate(template_text)
    _enable_llm(monkeypatch)
    calls = _install_fake_openai(monkeypatch, [bad, good])

    result = rephrase(template_text, facts)

    assert len(calls) == 2  # first attempt failed, retried with strict prompt
    assert result != template_text
    assert "9999" not in result


def test_rephrase_fallback_path_after_two_failures(monkeypatch):
    facts, template_text = _facts_and_template()
    bad = "Here's the rephrased text:\n9999 new genomes were found. This text is missing all the required sections."
    _enable_llm(monkeypatch)
    calls = _install_fake_openai(monkeypatch, [bad, bad])

    result = rephrase(template_text, facts)

    assert len(calls) == 2
    assert result == template_text


def test_interpret_reports_llm_used_true_on_success(monkeypatch):
    from bgclens.interpret import interpret

    good = _good_candidate(render_template(extract_facts(_pcoa_result())))
    _enable_llm(monkeypatch)
    _install_fake_openai(monkeypatch, [good])

    output = interpret(_pcoa_result(), use_llm=True)

    assert output["llm_used"] is True
    assert output["final_text"] != output["template_text"]


def test_interpret_reports_llm_used_false_on_persistent_failure(monkeypatch):
    from bgclens.interpret import interpret

    bad = "Here's the rephrased text:\n9999 new genomes were found. This text is missing all the required sections."
    _enable_llm(monkeypatch)
    _install_fake_openai(monkeypatch, [bad, bad])

    output = interpret(_pcoa_result(), use_llm=True)

    assert output["llm_used"] is False
    assert output["final_text"] == output["template_text"]
