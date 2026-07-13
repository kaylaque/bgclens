---
name: session-log
description: Write a session worksheet to docs/sessions/ documenting what was done, what's in progress, and what's next. Use at session start (to orient), at major checkpoints (to track), and at session end (to hand off). Commit the worksheet with the work.
---

# Session Log — worksheet skill

Write and maintain a session worksheet so that another agent (or you, returning tomorrow) can pick up exactly where this session left off.

## When to use

- **Session start**: create the worksheet before starting work to capture the goal
- **Major checkpoint**: update after completing each significant step
- **Session end**: fill in "what's next" before stopping — this is the hand-off note
- **When asked**: "log this session", "write a session note", "update the worksheet"

## Worksheet location

```
docs/sessions/YYYY-MM-DD-<slug>.md
```

Where `<slug>` is 2–4 words describing the session goal, kebab-cased.

Examples:
- `docs/sessions/2026-07-13-rewire-api-endpoints.md`
- `docs/sessions/2026-07-12-llm-extraction-refinement.md`

## Worksheet template

```markdown
# Session: <goal in one sentence>

**Date:** YYYY-MM-DD
**Branch:** <git branch name>
**Status:** IN PROGRESS | COMPLETE | BLOCKED

## Goal

<1–2 sentences: what this session is trying to accomplish and why>

## Context coming in

<What the previous state was. What was working, what was broken. Which Basecamp todos this maps to.>

## Steps completed

- [ ] Step 1 — <what was done> (<commit hash or "not committed yet">)
- [ ] Step 2 — <what was done>
- ...

## Current state

<What is true right now: what works, what's been tested, what's broken.>

## To continue from here

<Exact next actions for the next agent/session. Be specific: which file, which function, what to do.>

## Commits this session

```
<git log --oneline for this session's commits>
```

## Blockers / decisions needed

<Anything that requires human input or a decision that wasn't made in this session.>
```

## How to use this skill

### Session start

1. Run `git log --oneline -3` to see recent context
2. Create `docs/sessions/YYYY-MM-DD-<slug>.md` from the template above
3. Fill in: Goal, Context coming in, and the planned Steps
4. Do not start code work until the worksheet exists

### During the session

After each significant step:
1. Check off the completed step in the worksheet
2. Update "Current state" to reflect what's true now
3. Add the commit hash once committed

### Session end

1. Fill in "To continue from here" with exact next actions
2. Fill in "Commits this session" with `git log --oneline` output
3. Note any blockers
4. Commit the worksheet with the last code commit:

```bash
git add docs/sessions/YYYY-MM-DD-<slug>.md
git commit -m "chore(session): log YYYY-MM-DD <slug> session"
```

Or include it in the final substantive commit of the session.

## Naming and organisation

- One worksheet per session (not per day — a long day might have two focused sessions)
- If a session is a continuation of yesterday's, reference the prior worksheet in "Context coming in"
- `docs/sessions/` directory is committed (not gitignored) — session history is part of the repo

## Reference

Basecamp task queue: Hackathon Life Science → AI To-dos → MVP 1: BGCLens
