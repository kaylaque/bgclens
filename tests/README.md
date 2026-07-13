# Test suite — BGCLens

## Summary

| Suite | Files | Tests | Gate |
|-------|-------|-------|------|
| Unit | 14 | 148 | none (always run) |
| Integration — synthetic fixtures | 3 | 35 | none (always run) |
| Integration — real BGCFlow data | 1 | 13 | `BGCFLOW_PROCESSED_DIR` |
| Integration — live LLM | 1 | 3 | `BGCLENS_LLM_ENABLED=true` |
| **Total** | **19** | **199** | |

> **Note:** `README.md` (repo root) shows "82 passing" — that count predates the Jul 10–11 rewire and harness additions. The current always-safe count is **148 unit + 35 integration = 183 tests**. The root README badge will be updated post-submission.

Run always-safe tests:
```bash
make test-unit                          # unit only
uv run pytest tests/ -q --ignore=tests/integration/test_bgcflow_end_to_end.py --ignore=tests/integration/test_llm_goals.py
```

---

## Unit tests (`tests/unit/`)

| File | Tests | What it covers |
|------|-------|---------------|
| `test_catalog.py` | 13 | Catalog YAML loading, method smoke-tests, intent→method mapping, `get_impl()` dispatch |
| `test_intent.py` | 24 | `validate_intent()`, `filter_methods_for_intent()`, all 13 scientific-question (SQ) intents, `AnalysisRequest` model |
| `test_llm_harness.py` | 21 | Harnessed LLM endpoint: success path, one-shot repair loop, fallback to template, guard layer — all mocked, no network |
| `test_literature.py` | 16 | `rank_methods()`, OpenAlex co-occurrence logic, cache-key stability, multi-provider merge dedup |
| `test_interpret.py` | 10 | `extract_facts()`, `render_template()`, `guard_validate()` — no LLM call |
| `test_validation.py` | 11 | `evaluate()`, confidence band assignment (`band()`), validator/output key contracts |
| `test_manufacturability.py` | 9 | `compute_features()`, `compute_profile()`, tractability score, chassis hints, blocker flags |
| `test_detect.py` | 8 | `detect_project()` — antiSMASH/BiG-SCAPE/CheckM/GTDB-Tk pipeline detection from directory structure |
| `test_viz.py` | 8 | `recommend_chart()`, `render()`, SVG/PNG byte output, Okabe-Ito palette |
| `test_quarto_report.py` | 7 | `render()` — Quarto `.qmd` template rendering, `QuartoReport` model |
| `test_extract.py` | 7 | Literature extraction from abstracts: non-dict JSON guard, null `organism_terms`, confidence clamping, non-dict test |
| `test_compute.py` | 5 | `ResourceProfile`, `assess()`, `CostAssessment` — resource-gate logic |
| `test_csv_adapter.py` | 5 | `load_bgc_counts()` against real BGCFlow CSV shape |
| `test_model.py` | 3 | Canonical pydantic type instantiation smoke-tests (`FeatureCountTable`, `MetadataTable`, `PresenceAbsenceMatrix`, `ProjectManifest`) |

---

## Integration tests (`tests/integration/`)

### Always run (synthetic fixtures — no data required)

| File | Tests | What it covers |
|------|-------|---------------|
| `test_walking_skeleton.py` | 14 | Full pipeline: ingest → recommend → run → viz → interpret → `RunRecord`; uses `tests/fixtures/demo_project/` (8 genomes, 10 GCFs) |
| `test_cli_web_parity.py` | 12 | Provenance parity (Design §13): CLI path and web API path produce structurally identical `RunRecord` YAMLs for the same method + project |
| `test_web_api.py` | 9 | FastAPI surface: `/api/manifest`, `/api/intents`, `/api/recommend`, `/api/run`, `/api/report` endpoints via `TestClient` |

### Env-var gated

| File | Tests | Gate | What it covers |
|------|-------|------|---------------|
| `test_bgcflow_end_to_end.py` | 13 | `BGCFLOW_PROCESSED_DIR` (real data path) or `BGCLENS_RUN_BGCFLOW=1` (full pipeline, Linux + Snakemake) | Full BGCFlow → BGCLens round-trip on `mq_saccharopolyspora` or `Lactobacillus_delbrueckii` |
| `test_llm_goals.py` | 3 | `BGCLENS_LLM_ENABLED=true` + `.env` LLM config | Live LLM endpoint: hard goals hold after one-shot repair, guard strips invented values |

---

## Fixtures (`tests/fixtures/`)

`demo_project/` — synthetic BGCFlow project:
- 8 genomes, 10 GCFs, 6 BGC classes
- All BGCFlow pipeline outputs stubbed (antiSMASH, BiG-SCAPE, CheckM, GTDB-Tk, BiG-SLiCE, MASH)
- No network access required; used by all always-run integration tests

---

## Adding a test

- **Unit**: add `test_<module>.py` in `tests/unit/`, follow the pattern in the nearest existing file
- **Integration (synthetic)**: add to an existing file or create `test_<feature>.py` in `tests/integration/`; use `tests/fixtures/demo_project/` via the `demo_project` fixture
- **Integration (gated)**: gate with `@pytest.mark.skipif(not os.getenv("BGCFLOW_PROCESSED_DIR"), reason="...")`
- Update this file's count table when adding tests

---

## Known issues / tech debt

- `test_csv_adapter.py` uses hard-coded header rows from a real BGCFlow run — if BGCFlow changes its CSV schema, update the fixture headers in this file
- `test_llm_harness.py` mocks `openai` at module level; if the `openai` SDK version changes the `chat.completions.create()` call signature, the mock needs updating
- `test_bgcflow_end_to_end.py` requires Snakemake + Singularity for the full pipeline path — only runs in the CI Linux environment, never on Mac
