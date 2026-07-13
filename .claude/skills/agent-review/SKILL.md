---
name: agent-review
description: Persona-based self-review of the current diff before committing. Reviews through four lenses — correctness, code quality, scope compliance, and AI smells. Use before any commit on nontrivial changes.
---

# Agent Review — pre-commit persona checklist

Run this skill before committing any nontrivial change. It is a structured self-review, not a test run. Run `/agent-run` first to confirm the app works, then run this to check the code quality.

## When to use

- Before committing a feature, fix, or refactor
- Before opening a PR
- When asked to "review this", "check the diff", or "do a pre-commit review"

## Setup: get the diff

```bash
git diff HEAD          # unstaged + staged
git diff --cached      # staged only
```

Read the full diff before starting the review.

## The four personas

Work through each persona in order. For each finding, decide: **fix before commit** or **note as post-hackathon backlog**.

---

### Persona 1: Correctness Reviewer

Reads the code as if it will run in production on the judge's laptop at demo time.

Checks:
- [ ] Every changed function does what its name says — no silent early returns or swallowed exceptions
- [ ] Pydantic models: all required fields have values; Optional fields have `None` guards
- [ ] LLM calls: structured output enforced (JSON schema or tool use); free-text parsing is a red flag
- [ ] No fabricated data: UniProt IDs, PMIDs, sequences, taxids are never hardcoded
- [ ] API endpoints return the documented response shape (check against `bgclens_web/api/main.py`)
- [ ] Edge cases: empty result list, missing env vars, project directory not found — all handled gracefully
- [ ] No new `raise Exception` without a message; use specific exception types

---

### Persona 2: Code Quality Reviewer

Reads the code as a maintainer who'll inherit it post-hackathon.

Checks:
- [ ] Type hints on all new functions (not just params — return types too)
- [ ] No function longer than ~40 lines without a documented reason
- [ ] No inline long strings — prompts belong in `prompts/*.md`
- [ ] No duplicate logic introduced — check if a util in `bgclens/core/` already does this
- [ ] New tests exist for new behaviour (or a reason is documented for why not)
- [ ] No `print()` debugging left in; use `logging.getLogger(__name__)`
- [ ] `make lint` passes clean after the change

---

### Persona 3: Hackathon Scope Compliance

Reads the change against `CLAUDE.md` non-goals to catch scope creep.

Checks (flag anything that violates these):
- [ ] No new third data source added (only EuropePMC + UniProt per `CLAUDE.md`)
- [ ] No web UI beyond what was already in the plan (no auth, no accounts, no database)
- [ ] No fine-tuning or local protein language models
- [ ] No async added unless it saves >30% wall-time with evidence
- [ ] No dependency added without noting it
- [ ] API called < 100 times in any single run

---

### Persona 4: AI Smells Detector

Reads the code looking for patterns that indicate the LLM (or the developer rushing) made bad choices.

Checks:
- [ ] No hallucinated utility functions (functions referenced but not imported or defined)
- [ ] No "TODO: implement later" left in committed code
- [ ] No commented-out code blocks left in (delete, don't comment)
- [ ] No over-engineering: is this abstraction actually needed for the hackathon, or was it added "just in case"?
- [ ] No `# type: ignore` added without a comment explaining why
- [ ] No magic numbers without a named constant

---

## Output format

After all four persona passes, write a short summary:

```
## Review summary

**Persona 1 (Correctness):** [PASS / N findings]
**Persona 2 (Code Quality):** [PASS / N findings]
**Persona 3 (Scope):** [PASS / N findings]
**Persona 4 (AI Smells):** [PASS / N findings]

**Fix before commit:**
- <finding 1>
- <finding 2>

**Post-hackathon backlog:**
- <deferred item>

**Verdict:** COMMIT READY / FIX FIRST
```

If verdict is FIX FIRST: fix the "fix before commit" items, then re-run the review from the top.
