# BGCLens — PRD/Design Alignment Gap-Fill

**Date:** 2026-07-10  
**Source specs:** `prd-bgcflow-postprocessing-layer.md`, `design-bgclens-architecture.md`  
**Scope:** Fill gaps between current implementation and the PRD/design contracts

---

## 1. Problem

The implementation is structurally complete (all 8 engine layers exist) but has four gaps that break the design contracts or produce wrong output end-to-end.

---

## 2. Gaps and fixes

### Gap 1 — Engine API incomplete (Design §6)

**What the design specifies:**
```python
def visualize(result: AnalysisResult) -> list[VizSpec]
def interpret(result, viz: VizSpec) -> Interpretation
```
Both are top-level engine functions. CLI and web are "thin skins" that call only engine functions.

**What the code does:**  
`core/api.py` only exposes `open_project`, `recommend`, `run`. CLI and web import `bgclens.viz.render` and `bgclens.interpret.interpret` directly — logic lives in the surfaces, not the engine.

**Fix:**  
Add to `core/api.py`:
```python
def visualize(project: Project, result: dict) -> dict:
    """Render figure for result. Returns {chart_type, svg_bytes, png_bytes, alt_chart_types}."""

def interpret(project: Project, result: dict, *, use_llm: bool = True) -> dict:
    """Three-stage interpretation. Returns {facts, template_text, final_text, llm_used}."""
```
Update `bgclens_cli/__main__.py` and `bgclens_web/api/main.py` to call `api.visualize()` / `api.interpret()`.

---

### Gap 2 — Enrichment method ID mismatch (breaks run→interpret)

**Root cause (two-bug chain):**
1. `catalog/methods/enrichment.py:run()` returns `{"test": "fisher_exact", ...}` — uses key `"test"`, not `"method"`. Every other method sets `"method": "<id>"`.
2. `interpret/facts.py` dispatch dict maps `"fisher_exact"` → `_facts_enrichment`, but even if the key were `"method"`, the catalog entry's `id` is `fisher_enrichment` (not `fisher_exact`).

Result: enrichment results always fall to `_facts_generic` (wrong interpretation output).

**Fix:**
- `enrichment.py:run()` — add `"method": "fisher_enrichment"` to the return dict.
- `facts.py` dispatch — add `"fisher_enrichment": _facts_enrichment`; keep `"fisher_exact"` as alias.

---

### Gap 3 — RunRecord `request` field always empty (Design §13)

**What the design specifies:**
```yaml
bgclens_run:
  project: {...}
  request: {topic: ..., intent: comparison}
  run_spec: {method_id: permanova, params: {...}}
  ...
```

**What the code does:**  
`bgclens_cli/__main__.py:run_cmd` creates `RunRecord(project_path=..., run_spec=..., request={})` — `request` is always empty dict, losing the topic/intent provenance.

**Fix:**  
Populate `request` from the CLI parameters or session context. Since `run_cmd` takes `--method` and `--output` but not `--intent`/`--topic`, add optional `--intent` and `--topic` flags to `run_cmd` (defaulting to `""`) and populate `RunRecord(request={"method_id": method, "intent": intent or "", "topic": topic or ""}, ...)`.

---

### Gap 4 — US-009 session comparison missing in web

**What the PRD specifies (US-009):**  
Previous result is retained for side-by-side comparison (at least the last 2 runs).

**What the code does:**  
`_session["last_result"]` holds one dict, overwritten on each `/api/run` call.

**Fix:**
- Change `_session["run_history"]` to a list, append each result, truncate to last 2.
- Add `GET /api/history` endpoint returning the list.
- Update `/api/run` to append to history instead of overwriting `last_result`.

---

## 3. Files changed

| File | Change |
|------|--------|
| `bgclens/bgclens/core/api.py` | Add `visualize()` and `interpret()` engine functions |
| `bgclens/bgclens/catalog/methods/enrichment.py` | Add `"method": "fisher_enrichment"` to `run()` return |
| `bgclens/bgclens/interpret/facts.py` | Add `"fisher_enrichment"` dispatch key (alias `"fisher_exact"`) |
| `bgclens_cli/__main__.py` | Use `api.visualize()` + `api.interpret()`; add `--intent`/`--topic` to `run_cmd`; populate `RunRecord.request` |
| `bgclens_web/api/main.py` | Use `api.visualize()` + `api.interpret()`; add run history list; add `/api/history` endpoint |

---

## 4. What is NOT changing

- No changes to the method catalog YAML entries or implementations (they work correctly except the enrichment `"method"` key fix).
- No changes to literature service, compute advisor, viz renderer, or interpret templates.
- No new dependencies.
- No changes to test structure (tests already cover the layers being fixed).
