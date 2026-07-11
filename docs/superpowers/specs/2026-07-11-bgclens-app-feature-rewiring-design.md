# BGCLens — Rewiring As-Built Features Into the App

**Status:** Approved for implementation · **Date:** 2026-07-11

## Context

An audit (3 parallel agents over docs, front-end, and engine) found that BGCLens's
engine already ships working MVP versions of four intended features, but they are
**disconnected from the web app** (and one is broken):

| Feature | Engine state | App state |
|---|---|---|
| Manufacturability objective (Ph5) | Wired into `recommend()` but `compute_features` is **broken** (reads `.data` that doesn't exist → `tractability_score` always `0.0`) | Absent |
| Validation confidence band (Ph3) | `run()` computes green/amber/red | Computed then **stripped** before the response |
| Literature precedent (Ph2) | Works in `recommend()` | Hardcoded `use_literature:false`, no toggle |
| Quarto report (Ph4) | `report.render()` works | No endpoint |
| Extended `sq*` intents | 13 exist | Only 6 hardcoded |

Goal: **rewire + light enrichment**, all four features, **web-first with CLI kept in sync**.
No new science (no GEM/FBA, no sandbox test-gen, no queued jobs) — those stay walled off.

## Confirmed bugs (must fix)

1. **`manufacturability/features.py`** reads `project.bgc_counts.data` / `project.quality.data`
   (pandas-style) but `FeatureCountTable` only exposes `genome_ids`/`features`/`counts`/`to_numpy()`
   and `QualityTable` only `genome_ids`/`completeness`/`contamination`/`strain_heterogeneity`.
   Swallowed by try/except → always empty features, score `0.0`.
2. **`validation/__init__.py`** registry keys on `"diversity"`/`"clustering"` but catalog IDs are
   `"alpha_diversity"`/`"hierarchical_clustering"` → those two methods get **zero** validators → default amber.
3. **`manufacturability/profile.py`** boost-sets reference `"diversity"`/`"clustering"` (non-existent IDs) → dead boosts.

## User flow (enhanced 4-step wizard, in place)

- **Step 1 Load Project** — also surface `has_counts/has_taxonomy/has_network`.
- **Step 2 Goal** — all 13 intents grouped (Analytical / Research questions); **objective toggle**
  (Discovery ↔ Manufacturability); **literature toggle**; topic textarea.
- **Step 3 Method** — literature-support badges; when objective=manufacturability, a
  **manufacturability panel** (tractability, top class, chassis hint, blockers, honest note).
- **Step 4 Result** — figure + interpretation + downloads, plus **validation confidence band**
  (badge + per-check list) and a **Generate Report** button.

---

## CONTRACTS (single source of truth for all agents)

### Data contract — manufacturability annotation
`recommend()` appends to `recommendations[0].alternatives` exactly this dict when
`objective == "manufacturability"`:

```json
{
  "objective": "manufacturability",
  "tractability_score": 0.0,
  "top_class": "NRPS",
  "chassis_hint": {"organism": "E. coli", "reason": "..."},
  "blockers": ["needs PPTase for NRPS/PKS", "..."],
  "notes": ["what the genome cannot tell you: ..."]
}
```
- `chassis_hint` may be `null` if taxonomy/class unavailable. `blockers`/`notes` always lists (possibly empty).
- `ManufacturabilityProfile` (profile.py) carries `tractability_score`, `n_bgcs`, `top_class`,
  `chassis_hint`, `blockers`, `notes`. `core/api.py` annotation block builds the dict from it.

### API contract — web endpoints
**POST `/api/recommend`** — request gains `objective: str | null` (default null).
Response unchanged; `recommendations[].alternatives` now carries the annotation above.

**POST `/api/run`** — response ADDS (existing fields unchanged):
```json
{ "run_id": "…", "confidence_band": "green|amber|red|null",
  "validation_checks": [{"name":"…","passed":true,"detail":"…"}] }
```
`run_id` = stem of a saved `RunRecord` (mirror CLI `__main__.py:140-160`: build RunRecord, save
to a web session dir, e.g. `Path.home()/".cache/bgclens/web-runs"`).

**POST `/api/report`** (NEW) — request `{ "run_id": "…" }`.
Response `{ "qmd_path": "…", "html_path": "…|null", "html_b64": "…|null" }`.
Loads `RunRecord.from_yaml`, calls `bgclens.report.render(record, out_dir)`; base64 the HTML if produced.
404 if run_id unknown.

**GET `/api/intents`** — build from the `Intent` enum + `SQ_LABELS`, each item:
```json
{"value":"enrichment","label":"…","description":"…","group":"Analytical"}
```
`group` is `"Analytical"` for the 6 analytical intents, `"Research questions"` for the 7 `sq*`.

### CLI parity
`recommend` gains `--objective TEXT` (default none) → `AnalysisRequest(objective=…)`.
`run --output` and `report` already exist — no change.

---

## File ownership (no overlaps — parallel-safe)

- **G1 Manufacturability engine:** `bgclens/bgclens/manufacturability/*.py`, the manufacturability
  annotation block in `bgclens/bgclens/core/api.py` (~L184-195), `tests/unit/test_manufacturability.py`.
- **G2 Validation fix:** `bgclens/bgclens/validation/__init__.py`, `tests/unit/test_validation.py`.
- **G3 Web backend:** `bgclens_web/api/main.py`, `tests/integration/test_web_api.py`.
- **G4 Frontend:** `bgclens_web/frontend/index.html`.
- **G5 CLI parity:** `bgclens_cli/__main__.py`.

Integration + end-to-end verification against the live `Lactobacillus_delbrueckii` project is done
by the orchestrator after all groups land.

## Testing

- G1: build a real `FeatureCountTable` with data; assert non-zero tractability + correct `top_class`; chassis/blockers.
- G2: assert `alpha_diversity`/`hierarchical_clustering` now receive checks (non-empty validators).
- G3: `/api/recommend` with objective; `/api/run` returns `confidence_band` + `run_id`; `/api/report` yields a `.qmd`.
- All: `.venv/bin/python -m pytest` green for the touched area; no new dependencies.
