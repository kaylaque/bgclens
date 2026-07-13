# Post-hackathon backlog — deferred agentic infrastructure

Items from the [18-item agentic setup](https://x.com) that were evaluated and intentionally deferred
past the Jul 13 submission deadline. Revisit once BGCLens moves into ongoing development.

---

| # | Item | Deferred reason | Suggested first step |
|---|------|----------------|---------------------|
| 5 | **Pre-commit hooks** (`.pre-commit-config.yaml` with ruff + mypy auto-fix, or LLM-fix fallback) | Would slow last-day iteration velocity; `make lint` already covers the same surface manually | Add `.pre-commit-config.yaml` calling `ruff check --fix` + `mypy`; test that it doesn't break the dev loop |
| 6 | **Full cross-agent review** (codex/cursor/aider independent model review at plan/implement/wrap-up checkpoints, with distinct personas per domain) | Needs codex/cursor account setup and inter-tool scripting; not feasible in one night | Write a `tools/agent_review.sh` wrapper; add a `REVIEW.md` persona doc; wire into the session-log skill |
| 8 | **Agent feedback loop** (session debrief → committed doc → periodic ingestion + workflow improvement) | One-turn cycle now; feedback volume too low to justify the infrastructure | After 5+ sessions using `session-log`, run a review pass and distill improvements into `AGENTS.md` |
| 9 | **`tools/` / `bin/` helper scripts** (agent-accessible bash/python for repetitive tasks) | `Makefile` covers the current surface; overkill for hackathon | Create `tools/` when the second repeated-incantation pattern appears |
| 10 | **Commit-sweep skill** (periodic agent review across recent commits for cross-commit issues) | Commit volume too low; most changes in single PRs | Worth adding at ~50+ commits, or when the repo has multiple contributors |
| 11 | **`CODING_CONVENTIONS.md`** | `[tool.ruff]` + `[tool.mypy]` in `pyproject.toml` already enforce the conventions mechanically; a prose doc would drift | Add only if non-tool-enforceable conventions accumulate (naming patterns, module boundaries) |
| 12 | **Agent loop / night-shift skill** (autonomous multi-session orchestration) | Solo builder + deadline tonight; the loop infrastructure needs a stable task queue first | Implement after Basecamp API integration is stable and task IDs are programmatically accessible |
| 14 | **False-confidence test audit skill** (finds tests that pass but don't actually test what they claim) | Correct but time-consuming; current test suite is small enough to read manually | Schedule as a quarterly review skill; run after major refactors |
| 15 | **Visual regression tests** (screenshot compare, playwright, git-lfs) | Self-contained HTML wizard with no build step; VR harness setup cost outweighs benefit at this size | Add when the frontend stabilises post-hackathon; use playwright + `pytest-playwright` |
| 16 | **Performance benchmark tests** (`pytest-benchmark`, baseline committed) | No perf concern identified; all methods run in <30s on demo data | Add when a compute method starts taking >60s or when the GPU-box integration is the critical path |
| 17 | **Performance profiling tools** (agent-accessible scripts for targeted benchmarking) | Not a bottleneck yet | Add a `tools/profile_method.py` when a specific method is flagged as slow |
| 18 | **End-of-shift full validation** (all tests + perf + agent reviews + sweeps, run before stepping away) | Deadline is tonight; this is submission, not a shift | Wire as a `make validate` target combining `make lint`, `make test`, and `/agent-review` |
| 1 | **Standalone workflow doc** (repo-local `docs/WORKFLOW.md`) | Parent `hackathon-claude/WORKFLOW.md` already referenced from `CLAUDE.md` | Copy or symlink the parent doc if this repo is ever extracted to a standalone project |
| 13 | **Dedicated task queue doc** | Basecamp "MVP 1: BGCLens" already serves this per `CLAUDE.md`; a second queue would diverge | Wire a `tools/tasks.py` Basecamp API client if programmatic task access becomes needed |

---

## What was implemented tonight (Jul 13)

These items were added as the "middle path" pre-submission:

- `AGENTS.md` — agent router (item #0)
- `docs/RUNNING.md` — run/demo doc (partial item #3)
- `tests/README.md` — test enumeration doc (partial item #4)
- `.claude/skills/agent-run/` — lightweight "run the app" skill (item #3 surface)
- `.claude/skills/agent-review/` — persona self-review skill (lightweight item #6)
- `.claude/skills/session-log/` — session worksheet skill (lightweight item #7)
