# BGCLens — Implementation Audit

> What is built, where it is weak, and what to do about it.  
> Organized by the five topics from the pipeline teaching series (L1 → L4 → L2 → L3 → L5).

---

## L1 — Pipeline Seams (`open_project → recommend → run → interpret`)

### What is implemented

| Seam | File | Status |
|------|------|--------|
| `open_project()` | `bgclens/core/api.py:16` | ✅ Complete |
| `recommend()` | `bgclens/core/api.py:72` | ✅ Complete |
| `run()` | `bgclens/core/api.py:165` | ✅ Complete |
| `interpret()` | `bgclens/interpret/__init__.py` | ✅ Complete |
| Intent validation (`validate_intent`) | `bgclens/core/intent.py:53` | ✅ Complete |
| Method filtering (`filter_methods_for_intent`) | `bgclens/core/intent.py:82` | ✅ Complete |
| Compute cost gate (`advisor.assess`) | `bgclens/compute/advisor.py` | ✅ Complete |
| Provenance (`RunRecord`, `hash_project`) | `bgclens/core/provenance.py` | ✅ Complete |
| Session (last-2 result swap) | `bgclens/core/session.py` | ✅ Complete |
| DuckDB adapter | `bgclens/adapters/duckdb_adapter.py` | ✅ Complete |
| CSV/TSV fallback adapter | `bgclens/adapters/csv_adapter.py` | ✅ Complete |

### Weaknesses

1. **`_build_inputs()` is silent on missing data.** If a method's `requires` key names a field that isn't populated (e.g., `gcf_network`), the inputs dict is silently missing it. The method implementation then either crashes or returns nonsense. `validate_intent()` catches this for intents but not for individual method requirements beyond what the intent map covers.

2. **`recommend()` catches all exceptions from cost assessment and literature ranking.** The bare `except Exception: pass` on lines 115–117 and 150–152 means a bug in `advisor.assess()` or `OpenAlexProvider.support_for()` is silently swallowed. In production this would produce a recommendation with `cost_class="Safe"` even when the assessment code crashed.

3. **Session is in-memory only.** `session.py` uses a `deque(maxlen=2)` that lives for the duration of the process. Restarting the web server or CLI session loses all prior results. There is no persistence path for session state.

4. **`AnalysisRequest.method_hint` is parsed but not enforced.** The optional `method_hint` field exists to let CLI/web bypass the filter step, but `recommend()` does not use it — it always runs the full filter. The CLI `run` subcommand calls `run()` directly with `method_id`, bypassing `recommend()` entirely, which makes `method_hint` effectively dead code.

### Recommendations

- **Strengthen `_build_inputs()`**: add a pre-flight check that raises `ValueError` naming the missing field, rather than silently returning an incomplete inputs dict. This turns a confusing runtime crash inside the method into a clear error at the boundary.
- **Replace bare `except` with explicit narrow catches**: catch `httpx.HTTPError` and `bgclens.compute.CostEstimationError` separately; log the specific exception before continuing. Remove the catch-all.
- **Add a session persistence path**: write the last 2 `RunRecord` YAMLs to `~/.cache/bgclens/session/` on each `add_result()` call, and restore them on startup. This makes the "swap" feature useful across CLI invocations.
- **Either use `method_hint` in `recommend()` or remove it** from `AnalysisRequest`. Dead fields in a public API become permanent maintenance debt.

---

## L4 — Fixed-Field Paper Extraction

### What is implemented

| Component | File | Status |
|-----------|------|--------|
| Citation metadata extraction | `bgclens/literature/openalex.py:40–52` | ✅ Complete |
| `Citation` dataclass (6 fields) | `bgclens/literature/provider.py:7–13` | ✅ Complete |
| Abstract reconstruction from inverted index | `bgclens/literature/openalex.py:32–37` | ✅ Complete |

### What is NOT implemented (the gap)

| Component | Status |
|-----------|--------|
| `PaperExtract` schema (`github_repo`, `method_summary`, `input_types`, `output_types`, `is_open_source`, `replication_feasibility`) | ❌ Not built |
| LLM-driven structured extraction from abstract | ❌ Not built |
| `evidence_span` guard (verbatim-substring check per extracted field) | ❌ Not built |
| `bgclens/literature/extract.py` | ❌ Does not exist |

### Weaknesses

1. **Only metadata is extracted, not claims.** The current `Citation` captures 6 bibliographic fields. It cannot answer: "Does this paper have open-source code? What format does it take as input?" A recommender built only on citation metadata can credit papers but cannot characterize what they propose.

2. **Abstract is capped at 80 words.** `_abstract_from_inverted()[:200]` then `[:80]` (word count in the reconstruction) may truncate key information for longer abstracts. Methods described later in an abstract are invisible to the co-occurrence gate.

3. **No confidence signal per citation.** `Citation` has no field indicating how strongly the paper's content matches the query — all validated citations are treated as equally relevant. A paper where the method term appears only in the references list passes the gate the same as one where it is the central contribution.

### Recommendations

- **Build `bgclens/literature/extract.py`** with the `PaperExtract` + `FieldEvidence` schema sketched in L4. Follow the same three-stage pattern as `bgclens/interpret/`: deterministic pre-extraction (regex for GitHub URLs) → structured LLM extraction → `evidence_span` verbatim-substring guard.
- **Raise the abstract reconstruction cap**: increase from 80 words to 150–200 words. The 80-word cap was set conservatively for token budget reasons; abstracts are typically 150–250 words, and truncating at 80 misses the methods and results sections.
- **Add a `relevance_score` field to `Citation`**: a float 0–1 derived from the number of topic-term co-occurrences in the abstract. This allows the ranker to distinguish "strong match" from "technically co-occurring" citations.

---

## L2 — Paper Search (OpenAlex + Co-occurrence Ranker)

### What is implemented

| Component | File | Status |
|-----------|------|--------|
| OpenAlex REST client | `bgclens/literature/openalex.py` | ✅ Complete |
| Abstract inverted-index reconstruction | `bgclens/literature/openalex.py:32–37` | ✅ Complete |
| Co-occurrence gate (`m_hit AND t_hit`) | `bgclens/literature/openalex.py:94–103` | ✅ Complete |
| Support-level scoring (strong/moderate/weak/none) | `bgclens/literature/openalex.py:61–68` | ✅ Complete |
| `rank_methods()` with `_LEVEL_ORDER` sort | `bgclens/literature/ranker.py` | ✅ Complete |
| Disk cache (diskcache, `~/.cache/bgclens/`) | `bgclens/literature/cache.py` | ✅ Complete |
| Offline fallback (`_offline_fallback`) | `bgclens/literature/ranker.py` | ✅ Complete |
| Rate limiting (0.12s sleep between requests) | `bgclens/literature/openalex.py:11` | ✅ Complete |

### Weaknesses

1. **Cache has no TTL.** Results are cached permanently. A paper published after the first cache hit will never appear until the cache is manually cleared. For a hackathon this is acceptable; for ongoing use it means the literature layer silently ages.

2. **Only the first 3 topic terms are used in the boolean query** (`topic_terms[:3]`). Richer topic descriptions with more specificity (e.g., `["termite gut", "lignocellulose", "GH48", "cellulase", "metagenome"]`) are silently truncated to 3 terms before the query is built. The co-occurrence gate still checks all topic terms at the abstract level, but the OpenAlex ranking biases toward the first 3 only.

3. **`support_for()` in `OpenAlexProvider` has a bug**: the loop signature `for method_id, method_term in zip(method_terms, method_terms)` zips the list with itself, so `method_id` and `method_term` are always the same string. The intended pattern was `zip(method_ids, method_terms)` where IDs and display names can differ. The method works correctly by accident (because both are the same list), but the intent is obscured.

4. **No window-year filter is applied at the HTTP level.** `window_years` is accepted as a parameter but the OpenAlex query does not include a `filter=publication_year:>YYYY` clause. Older papers are included in results without being gated by recency.

### Recommendations

- **Add TTL to cache**: set `expire=7 * 24 * 3600` (7 days) on `cache.set()` calls. Stale-while-revalidate is not needed for this use case; simple expiry is sufficient.
- **Increase the topic-term query cap from 3 to 5**: OpenAlex's boolean query parser handles up to 5 terms reliably. Test with `["termite gut", "lignocellulose", "cellulase", "BGC", "secondary metabolite"]` before raising further.
- **Fix the `zip` bug**: change `for method_id, method_term in zip(method_terms, method_terms)` to `for method_term in method_terms`. The `method_id` alias was misleading — use `method_term` throughout.
- **Apply the window-year filter at the HTTP level**: add `filter=publication_year:>{current_year - window_years}` to `_search_works()` params when `window_years` is set. This reduces irrelevant results from older literature and improves the precision of support-level scoring.

---

## L3 — MCP / Connector Surface

### What is implemented

| Component | File | Status |
|-----------|------|--------|
| `LiteratureProvider` Protocol | `bgclens/literature/provider.py:34–42` | ✅ Complete |
| `@runtime_checkable` decorator | `bgclens/literature/provider.py:34` | ✅ Complete |
| `Citation`, `MethodLiteratureSupport`, `LiteratureRanking` dataclasses | `bgclens/literature/provider.py:6–31` | ✅ Complete |
| `OpenAlexProvider` (single wired connector) | `bgclens/literature/openalex.py` | ✅ Complete |

### What is NOT implemented

| Connector | Status |
|-----------|--------|
| Europe PMC | ❌ Not built |
| PubMed E-utilities | ❌ Not built |
| Semantic Scholar | ❌ Not built |
| CrossRef | ❌ Not built |
| bioRxiv / medRxiv | ❌ Not built |
| UniProt (enzyme-anchored) | ❌ Not built |
| MIBiG (curated BGC literature) | ❌ Not built |
| Connector registry / config-driven selection | ❌ Not built |

### Weaknesses

1. **Only one connector is wired; there is no selection mechanism.** `recommend()` in `api.py` hardcodes `OpenAlexProvider()`. There is no way to switch providers via config, CLI flag, or web UI without modifying source code.

2. **The Protocol is not enforced at call sites.** `recommend()` calls `OpenAlexProvider()` directly by import, bypassing any `isinstance(provider, LiteratureProvider)` check. The `@runtime_checkable` decorator is present but never exercised in the actual call path — only in tests.

3. **No multi-provider aggregation.** The Protocol describes a single-provider interface. There is no combiner that calls multiple providers and merges results (e.g., OpenAlex for breadth, MIBiG for domain precision). For BGC-specific research, MIBiG citations would dramatically increase precision.

### Recommendations

- **Add a `BGCLENS_LITERATURE_PROVIDER` env var** (default: `openalex`) and a provider factory function in `bgclens/literature/__init__.py` that maps the value to a provider instance. This makes switching providers a config change, not a code change.
- **Add `isinstance` check at the `recommend()` call site**: `assert isinstance(provider, LiteratureProvider), f"..."`. This makes the `@runtime_checkable` decorator earn its keep.
- **Build `EuropePMCProvider` next** (highest priority for life-science coverage): it returns plain-text abstracts (no inverted-index reconstruction needed), covers open-access full text, and is the primary connector for the project's target domain. Estimated 40 lines using the pattern in L3.
- **Build `MIBiGProvider` for BGC-specific queries**: MIBiG's structured entries (cluster → compound → reference) give far higher precision than keyword search for BGC family queries. Recommended for use as a secondary provider layered on top of OpenAlex results.

---

## L5 — Alignment Tests

### What is implemented

| Test | File | Type | Status |
|------|------|------|--------|
| Guard: fabricated DOI stripped | `tests/unit/test_interpret.py` | Paper-principle | ✅ |
| Guard: hallucinated number stripped | `tests/unit/test_interpret.py` | Paper-principle | ✅ |
| Guard: fact numbers allowed | `tests/unit/test_interpret.py` | Paper-principle | ✅ |
| LLM harness repair loop | `tests/unit/test_llm_harness.py` | Paper-principle | ✅ |
| Catalog validation (`validate_catalog`) | `tests/unit/test_catalog.py` | Paper-principle | ✅ |
| Walking skeleton (full pipeline on demo fixture) | `tests/integration/test_walking_skeleton.py` | Dataset-divergence | ✅ (11 tests) |
| CLI ↔ web provenance parity | `tests/integration/test_cli_web_parity.py` | Paper-principle | ✅ (11 tests) |
| Web API endpoints | `tests/integration/test_web_api.py` | Integration | ✅ (6 tests) |
| BGCFlow pre-computed path | `tests/integration/test_bgcflow_end_to_end.py` | Dataset-divergence | ✅ (5 tests, env-gated) |
| BGCFlow full pipeline (Linux/Snakemake) | `tests/integration/test_bgcflow_end_to_end.py` | Dataset-divergence | ✅ (6 tests, marker-gated) |

### Weaknesses

1. **No literature layer tests.** There are no unit tests for `openalex.py`, `ranker.py`, or `cache.py` with offline fixtures. The co-occurrence gate logic (the anti-hallucination mechanism for literature) is completely untested in the current suite. This is a paper-principle gap — the gate is the correctness claim.

2. **No `PaperExtract` guard tests** (because `extract.py` doesn't exist yet, but this is noted for when it is built).

3. **Walking skeleton uses `genus` not `clade` for group splits.** `test_07` in `test_walking_skeleton.py` uses `grouping_col="genus"` because the CSV adapter does not surface the `clade` column from `df_gtdb_meta.csv`. This is a silent data-layer gap: the column is present in the fixture but not loaded.

4. **No negative-path tests for `recommend()`.** There is no test asserting that `recommend()` returns `valid=False` when an intent's required data is missing. The guard (`validate_intent`) is tested implicitly through the walking skeleton but never explicitly in isolation.

5. **Test count in README is stale** if tests are added without updating the badge (`82 passing`).

### Recommendations

- **Add `tests/unit/test_literature.py`** with offline fixtures:
  - `test_cooccurrence_gate_requires_both_hits` — mock two works, one with only `m_hit`, one with both; assert only the latter is in `validated`.
  - `test_support_level_thresholds` — assert `_support_level(0)="none"`, `_support_level(1)="weak"`, `_support_level(3)="moderate"`, `_support_level(10)="strong"`.
  - `test_abstract_reconstruction` — given a known inverted index, assert the reconstructed string matches the expected sentence.
  - `test_offline_fallback_returns_none_for_all` — mock a network error; assert all methods return `support_level="none"` and `LiteratureRanking.offline=True`.
- **Add explicit `validate_intent()` unit tests**: one test per intent that asserts `valid=False` when the required table is `None` in the project, and `valid=True` when it is populated.
- **Fix the `clade` column loading** in `csv_adapter.py`: add `"clade"` to the column-mapping dict in `load_metadata()`. Then update `test_07` to use `grouping_col="clade"` to match the fixture's intended structure.
- **Add a CI step that re-counts passing tests** and updates the README badge automatically, or remove the hard-coded count and replace it with a badge generated from the test report.

---

## Cross-cutting summary

| Layer | Completeness | Biggest gap | Priority fix |
|-------|-------------|-------------|--------------|
| Pipeline seams (L1) | High — all 4 seams work end-to-end | Silent failure in `_build_inputs()` | Strengthen input validation |
| Paper extraction (L4) | Low — metadata only, no claim extraction | `PaperExtract` schema not built | Build `literature/extract.py` |
| Paper search (L2) | Medium — works but has precision gaps | No TTL, query cap of 3 terms, `zip` bug | Fix bug + add TTL |
| Connector surface (L3) | Low — one connector, no selection mechanism | No config-driven provider switching | Add env-var provider factory |
| Alignment tests (L5) | Medium — core tests present, literature untested | Zero tests for co-occurrence gate | Add `test_literature.py` |

**Most impactful next step:** build `bgclens/literature/extract.py` (`PaperExtract` + `evidence_span` guard). It closes the largest functional gap (L4), and once it exists, it unlocks the connector surface (L3) to become genuinely useful — having 8 connectors only matters if the system can extract structured claims from what they return.
