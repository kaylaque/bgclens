---
name: agent-run
description: Run and verify the BGCLens app after a nontrivial change. Use after any change to bgclens/, bgclens_cli/, bgclens_web/, or catalog/. Starts the web UI, walks the four-step wizard, and confirms the changed surface works end-to-end before committing.
---

# Agent Run — verify the app works after a change

Invoke this skill after any nontrivial code change. Do not report a task as complete without running the app first.

## When to use

- After any edit to `bgclens/`, `bgclens_cli/`, `bgclens_web/`, or `bgclens/catalog/entries/`
- Before committing if the change touches an API endpoint, a compute method, or the web UI
- When asked to "run the app", "test this works", or "verify the change"

## Steps

### 1. Lint + unit tests (always first)

```bash
make lint        # ruff + mypy — fix any errors before continuing
make test-unit   # all 148 unit tests must pass
```

If either fails: stop, fix, then restart this skill.

### 2. Start the web UI

```bash
make web         # starts bgclens web at http://localhost:8766 --no-browser
```

Run this in the background (use `run_in_background: true` in Bash tool).

### 3. Walk the v2 two-page flow

Using the FastAPI endpoints (v2 flow: ingest → clusters → run-batch → lock → chat):

```bash
# Check the app is up
curl -s http://localhost:8766/api/health | python3 -m json.tool

# Load project
curl -s -X POST http://localhost:8766/api/open \
  -H "Content-Type: application/json" \
  -d '{"path": "tests/fixtures/demo_project"}' | python3 -m json.tool | head -15

# List clusters (v2 P1 cluster profile view)
curl -s "http://localhost:8766/api/clusters?path=tests/fixtures/demo_project" \
  | python3 -m json.tool | head -30

# Run batch (v2 per-cluster fan-out)
curl -s -X POST http://localhost:8766/api/run-batch \
  -H "Content-Type: application/json" \
  -d '{"path": "tests/fixtures/demo_project", "method_ids": ["alpha_diversity"], "use_llm": false}' \
  | python3 -m json.tool | head -20

# Chat (v2 grounded Q&A)
curl -s -X POST http://localhost:8766/api/chat \
  -H "Content-Type: application/json" \
  -d '{"path": "tests/fixtures/demo_project", "message": "How many GCFs are in this project?"}' \
  | python3 -m json.tool
```

Legacy single-method flow (still works for backward-compat):

```bash
curl -s "http://localhost:8766/api/recommend" \
  -H "Content-Type: application/json" \
  -d '{"path": "tests/fixtures/demo_project", "intent": "diversity", "topic": "BGC diversity"}' \
  | python3 -m json.tool | head -20
```

### 4. Verify the specific changed surface

Identify which endpoint, method, or UI path your change affects. Hit it directly. Check:
- No 500 errors
- The response shape matches the model (pydantic fields present, no nulls where values expected)
- If it's a viz change: SVG bytes non-empty; if it's an interpret change: template prose non-empty

### 5. Report

State clearly:
- Which endpoints/methods were tested
- What the response looked like (first 5 fields)
- Whether the changed surface produced the expected output
- Any unexpected warnings or log lines

If anything fails: do not commit. Fix and re-run from step 1.

## Reference

Full environment and gating details: `docs/RUNNING.md`
