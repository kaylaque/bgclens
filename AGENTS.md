# AGENTS.md — BGCLens agent router
# Summary (first-7-line scannable block):
# Project: BGCLens — post-processing + interpretation layer for BGCFlow output
# Rules:   CLAUDE.md (project constraints) · ../WORKFLOW.md (session workflow)
# Run:     docs/RUNNING.md  |  Tests: tests/README.md  |  Code: pyproject.toml [tool.ruff/mypy]
# Arch:    docs/design-bgclens-architecture.md · docs/prd-bgcflow-postprocessing-layer.md
# Phases:  docs/phase{1..5}-bgclens-*.md  |  Audit: docs/implementation-audit.md
# Tasks:   Basecamp "Hackathon Life Science" → "AI To-dos" → "MVP 1: BGCLens"
# Skills:  .claude/skills/{agent-run,agent-review,session-log,daily-standup,log-notes,pitch-deck,teach}

---

## 1. Start here every session

Read in this order before touching code:

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project constraints, non-goals, LLM usage rules, success criteria |
| `../WORKFLOW.md` | Session workflow (plan → implement → verify → commit) |
| `docs/RUNNING.md` | How to run, test, and demo the app |

---

## 2. Architecture and design

| File | Contents |
|------|---------|
| `docs/design-bgclens-architecture.md` | Module map, data-flow, API surface |
| `docs/prd-bgcflow-postprocessing-layer.md` | Product requirements document |
| `docs/phase1-bgclens-literature-precedent.md` | Phase 1: literature / OpenAlex |
| `docs/phase2-bgclens-validation-confidence.md` | Phase 2: validation harness |
| `docs/phase3-bgclens-quarto-report.md` | Phase 3: Quarto report renderer |
| `docs/phase4-bgclens-manufacturability.md` | Phase 4: manufacturability scoring |
| `docs/phase5-bgclens-rewire.md` | Phase 5: web/CLI wiring |
| `docs/implementation-audit.md` | As-built audit — what each phase actually shipped |

---

## 3. Source layout (what lives where)

```
bgclens/              engine (all logic)
  adapters/           BGCFlow project detection + CSV/DuckDB loaders
  catalog/            method YAML entries + Python implementations
  compute/            resource probe + compute cost advisor
  core/               engine API, session, provenance, config
  interpret/          facts → template → LLM phrasing + guard
  literature/         OpenAlex client + co-occurrence ranker
  manufacturability/  tractability scoring + chassis hints
  model/              canonical pydantic types
  report/             Quarto .qmd renderer
  validation/         confidence bands + validation checks
  viz/                matplotlib renderers → SVG + PNG bytes
bgclens_cli/          thin Typer CLI (open/recommend/run/web/report)
bgclens_web/
  api/main.py         FastAPI wrapper (5 endpoints: /api/intents /manifest /recommend /run /report)
  frontend/           self-contained HTML wizard (no build step)
tests/
  fixtures/           synthetic demo project (8 genomes, 10 GCFs)
  unit/               per-module unit tests (148 tests, always-on)
  integration/        walking skeleton + parity + web API + BGCFlow e2e
```

---

## 4. Skills available in this session

| Skill | Invoke | Purpose |
|-------|--------|---------|
| `agent-run` | `/agent-run` | Run and screenshot the app after a change |
| `agent-review` | `/agent-review` | Persona-based self-review before committing |
| `session-log` | `/session-log` | Write a session worksheet to `docs/sessions/` |
| `daily-standup` | `/daily-standup` | Add a sprint standup note |
| `log-notes` | `/log-notes` | Quick capture to journal |
| `pitch-deck` | `/pitch-deck` | Build or update Marp deck |
| `teach` | `/teach` | Stateful learning session in `hackathon_vault/learn/` |

---

## 5. Coding conventions

Enforced by tooling — do not duplicate in prose:

- **Linter**: `make lint` → `ruff check` + `mypy` (config in `pyproject.toml`)
- **Type hints**: everywhere, pydantic for all candidate/record schemas
- **Structured LLM output**: every call returns JSON schema; no regex-parsing free text
- **No async** unless it saves >30% wall-time
- **No inline long prompts**: templates live in `prompts/*.md`
- **No fabrication**: never invent UniProt IDs, PMIDs, sequences, or accession numbers

---

## 6. Task queue

Tasks tracked in Basecamp: **Hackathon Life Science → AI To-dos → MVP 1: BGCLens**.

Two open todos as of Jul 12:
- "refine the LLM extraction process" — prompt tuning + empty-candidate fallback
- "refine tool call/agentic process needed" — explicit multi-step call sequence

---

## 7. Post-hackathon backlog

Items intentionally deferred to after submission: `docs/POST_HACKATHON_BACKLOG.md`
