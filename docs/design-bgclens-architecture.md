# Architecture & Design: BGCLens

> Companion to `prd-bgcflow-postprocessing-layer.md`. The PRD defines *what* and *why*; this document defines *how the pieces fit* and fixes the contracts everything else depends on.
>
> **Status: as-built.** Reconciled against the codebase 2026-07-10. Sections marked **[AS BUILT]** describe what the code does; where the implementation diverged from the original design, the divergence is stated explicitly rather than quietly edited away. All `[DECIDE]` markers have been resolved.

## 1. Purpose of this document

The PRD is a spec, not an architecture. Three things must exist before implementation is safe: (a) the data contracts that are the spine of every feature, (b) the engine↔UI boundary that makes CLI/web parity real rather than aspirational, and (c) resolutions to the architectural forks buried in the PRD's Open Questions.

This document now serves a second purpose: it is the accurate map of the shipped system. Where the built system is *narrower* than the design (the engine API) or *wider* (validation, manufacturability, reporting), both are recorded.

## 2. Design principles (load-bearing decisions)

These are the decisions everything else hangs off. Get them wrong and the rework is expensive. Each is annotated with whether the built system upholds it.

1. **The engine is the product; the CLI and web app are thin skins.** All logic — ingestion, method selection, execution, figure rendering, interpretation — lives in one importable Python library. The CLI and web API call the *same functions*. Neither surface contains analysis logic. This is the only way the "CLI run == web run" success metric is achievable.
   → **Upheld in substance.** No analysis logic lives in either surface. But the surfaces import `bgclens.viz` and `bgclens.interpret` directly rather than going through `core.api` (§6). The principle holds; the stated single entry point does not.

2. **Figures are rendered in the engine, not the browser.** Rendering uses matplotlib inside the engine and emits SVG+PNG bytes. The web frontend *displays* those bytes; it does not re-plot. Consequence: a CLI run and a web run produce byte-identical figures, and figure code is testable without a browser.
   → **Upheld.**

3. **Science is deterministic; the LLM only touches prose.** Every number, statistic, and claim is computed by tested code. The LLM, where used, rephrases already-correct template text and is never given raw data or allowed to introduce a number. This makes the tool defensible and the interpretation layer unit-testable.
   → **Upheld, and hardened.** Four deterministic hard goals gate every LLM candidate; failure returns the template verbatim (§12).

4. **The method catalog is data, not code.** Methods are declared in YAML and resolve to registered implementations. Adding a method is a data + plugin change, never an engine change.
   → **Upheld.** Seven entries, glob-loaded, CI-validated.

5. **Read-only, strictly downstream.** BGCLens never invokes or mutates BGCFlow. It only reads a finished project's outputs.
   → **Upheld.**

6. **Provenance is not optional.** Every run writes a complete, replayable record. Provenance *is* the config-export format — the same artifact reproduces a run and documents it.
   → **Half-upheld.** Every run writes a `RunRecord`, and CLI/web records are identical (11 parity tests). But **nothing reads one back** — the record documents a run, it cannot yet replay one (§13). The word "replayable" is currently aspirational.

## 3. System context

```
  ┌─────────────┐     finished project (read-only)     ┌──────────────────────────────┐
  │  BGCFlow    │ ──────────────────────────────────▶  │           BGCLens             │
  │  run +      │   data/processed/<project>/          │                              │
  │ build report│   ├─ DuckDB OLAP db                  │  engine (library)            │
  └─────────────┘   └─ CSV/TSV summary tables          │   ├─ adapters (ingest)       │
                                                       │   ├─ canonical model         │
  ┌──────────────────────┐   scholarly queries         │   ├─ catalog + methods       │
  │ OpenAlex (default)   │ ◀─────────────────────────▶ │   ├─ literature service      │
  │ Europe PMC · MIBiG   │   cited, ranked methods     │   ├─ compute advisor         │
  └──────────────────────┘                             │   ├─ viz (matplotlib)        │
                                                       │   ├─ interpret (+ LLM guard) │
  ┌──────────────────────┐   cores / RAM / sinfo       │   ├─ validation  (§12a NEW)  │
  │ local machine /      │ ◀───────────────────────    │   ├─ manufacturability (12b) │
  │ SLURM (read-only)    │                             │   ├─ report → Quarto (13a)   │
  └──────────────────────┘                             │   └─ provenance              │
                                                       │                              │
  ┌──────────────────────┐   optional prose rephrase   │  surfaces (thin):            │
  │ OpenAI-compatible    │ ◀─────────────────────────▶ │   ├─ CLI (Typer, 5 cmds)     │
  │ LLM endpoint         │   facts + template only     │   └─ Web API (FastAPI)       │
  └──────────────────────┘   (never raw data)          │       + offline HTML wizard  │
                                                       └──────────────────────────────┘
```

## 4. Layered architecture  **[AS BUILT]**

The design specified eight components. **Eleven shipped** — three were added during implementation. Data flows downward; provenance is cross-cutting.

**As designed:**

1. **Adapters** — read BGCFlow output (DuckDB first, CSV/TSV fallback), detect which pipelines ran, emit a **ProjectManifest**.
2. **Canonical model** — normalize heterogeneous outputs into a small fixed set of types joined on `genome_id` (Section 5).
3. **Method catalog** — versioned YAML registry of methods + their registered implementations, constraints, cost models, citations (Section 8).
4. **Literature service** — provider abstraction that ranks candidate methods by literature support and attaches real citations (Section 9).
5. **Compute advisor** — estimates cost, detects resources, classifies Safe/Heavy/Likely-to-fail, recommends lighter alternatives (Section 10).
6. **Analysis engine** — the orchestrator that ties the above into the request→recommend→run flow (Section 6).
7. **Visualization service** — result→recommended chart→rendered SVG+PNG (Section 11).
8. **Interpretation service** — computed result→grounded facts→narrative with caveats + citations (Section 12).

**Added during implementation:**

9. **Validation harness** (`validation/`) — deterministic per-method internal-coherence checks over the result dict, banded green/amber/red. Never raises. Distinct from `check_assumptions`, which warns about *validity*; this asserts *coherence* (Section 12a).
10. **Manufacturability** (`manufacturability/`) — Tier-A tractability features from BGC class composition, driving an optional recommendation re-ranking objective (Section 12b).
11. **Report renderer** (`report/`) — a persisted `RunRecord` → Quarto `.qmd` (+ HTML when `quarto` is on PATH). Never raises (Section 13a).

Components 9–11 are leaf modules: each depends on at most `bgclens.model`, and nothing depends on them except `core/api.py` and the CLI. They can be removed without touching the analysis path.

## 5. The canonical data model (the spine)

Everything downstream depends on these contracts, so they're defined first and frozen early. Adapters map BGCFlow's many tables *into* these; methods only ever see these. Sketches are illustrative (pydantic/dataclass style).

```python
class ProjectManifest:
    project_name: str
    source_path: Path
    duckdb_path: Path | None
    available_pipelines: set[str]        # {"antismash","bigscape","checkm",...}
    datasets: dict[str, DatasetHandle]   # keyed dataset descriptors + shapes

class PresenceAbsenceMatrix:             # e.g. GCFs × genomes
    rows: list[str]                      # feature ids (e.g. GCF ids)
    cols: list[str]                      # genome ids
    values: NDArray[bool | int]
    row_meta: FeatureTable | None
    col_meta: MetadataTable              # joined taxonomy/quality

class FeatureCountTable:                 # BGC/class counts per genome
    genome_ids: list[str]
    features: list[str]                  # e.g. biosynthetic classes
    counts: NDArray[int]

class TaxonomyTable / QualityTable:      # GTDB-Tk / CheckM, keyed by genome_id
class NetworkEdgeList:                   # GCF similarity network
    nodes: list[str]; edges: list[tuple[str,str,float]]
class MetadataTable:                     # the join hub, keyed by genome_id
```

**Rule:** all cross-dataset joins happen on `genome_id`; `MetadataTable` is the join hub. If a method needs data that isn't loadable into one of these types, it is not in the catalog. This keeps the method↔data contract closed and testable.

All six types shipped as pydantic models in `model/`. The walking skeleton (demo project → PCoA → figure → templated interpretation) is `tests/integration/test_walking_skeleton.py`.

## 5a. The intent space  **[AS BUILT — expanded 6 → 13]**

The design assumed six statistical-family intents. Implementation added seven **scientific-question (SQ)** intents that let a researcher pick by the question they're asking rather than the statistical family that answers it. Both spaces coexist; catalog entries tag themselves into each via `intents:` and `sq:`.

| SQ intent | Label (`SQ_LABELS`) | Requires |
|---|---|---|
| `sq1_inventory` | Inventory — what / how many BGCs? | `bgc_counts` |
| `sq2_novelty` | Novelty — known vs new? | `gcf_presence_absence` |
| `sq3_prioritization` | Prioritization — which to chase in the lab? | `gcf_presence_absence` |
| `sq4_distribution` | Distribution — how spread across strains/taxa? | `bgc_counts` |
| `sq5_diversity` | Diversity / sampling — how diverse, is it saturated? | `gcf_presence_absence` |
| `sq6_genomic_context` | Genomic context — core vs accessory, resistance, HGT | `gcf_network` |
| `sq7_association` | Association — do BGCs track phenotype/metadata? | `gcf_presence_absence` |

The original six (`enrichment`, `diversity`, `ordination`, `clustering`, `comparison`, `network_structure`) remain and have no `SQ_LABELS` entry.

`validate_intent()` maps each intent to its required dataset and, on failure, names the BGCFlow tool that must be run. `MissingRequirementError` carries that message.

**Gap:** the web `GET /api/intents` endpoint has not been updated and exposes only the original six.

## 6. Core engine contracts  **[AS BUILT — diverged]**

The design specified a five-function engine API. **Three shipped.** `visualize()` and `interpret()` were never added to `core/api.py`; they live in `bgclens.viz` and `bgclens.interpret` and are imported directly by both surfaces.

```python
# core/api.py — the actual engine API surface
def open_project(path: Path | str) -> Project

def recommend(project, request: AnalysisRequest, use_literature: bool = True
             ) -> tuple[IntentValidation, list[MethodRecommendation]]
    # intent validation → catalog filter → assumption checks → cost class (§10)
    # → literature rank (§9) → optional manufacturability reorder (§12b)

def run(project, method_id: str, params: dict | None = None) -> dict
    # executes, then attaches: _assumption_warnings, _method_id, _provenance,
    #                          _confidence_band, _validation_checks   (§12a)

class MissingRequirementError(ValueError): ...
    # raised by _build_inputs when a required dataset is absent;
    # the message names the BGCFlow tool that must be run

# Called directly by both surfaces — NOT part of core.api:
bgclens.viz.render(result, metadata)         -> tuple[bytes, bytes]   # (svg, png)
bgclens.interpret.interpret(result, assumption_warnings=..., use_llm=...) -> dict
```

**Value objects (as built):**

```python
AnalysisRequest  = {topic: str, intent: Intent, method_hint: str|None,
                    objective: str|None}          # objective: "manufacturability"
MethodRecommendation = {method_id, method_name, intent, cost_class, cost_reason,
                        assumption_warnings, literature_support, literature_citations,
                        is_recommended, alternatives}
IntentValidation = {valid: bool, intent: str, missing_data: list[str], suggestion: str}
```

Flow: `open_project → recommend → (user picks) → run → viz.render → interpret.interpret → persist RunRecord`.

**On the divergence.** Parity is not harmed: both surfaces import the same `viz`/`interpret` modules, and the 11-test parity suite asserts identical provenance across CLI and web. But the *stated* boundary — "surfaces call only `core.api`" — is not what the code does. Two options, unresolved:

- **(a) Ratify it.** Declare `viz` and `interpret` public engine modules; the boundary is `bgclens.*`, not `bgclens.core.api`. Cheapest, and honest about the shape that emerged.
- **(b) Restore it.** Add thin `api.visualize()` / `api.interpret()` wrappers and update both surfaces. Recovers a single import point, at the cost of one indirection.

**Method swap (US-009)** re-enters at `recommend`/`run` with the same loaded `Project` — no disk re-read. **Not built:** retention of prior `RunRecord`s for comparison. The web session holds only `last_result`, overwritten each run. This blocks the Phase-2 comparison dashboard.

## 7. Engine↔UI boundary & CLI/web parity  **[AS BUILT]**

Both surfaces are thin translators between user input and the engine.

- **CLI (Typer) — 5 commands:** `open`, `recommend`, `run`, `report`, `web`.
  `run` takes `--method`, `--params` (JSON string), `--output`, `--no-llm`.
  **Not built:** the specified non-interactive config-file mode, and interactive prompting.
- **Web (FastAPI + vanilla HTML) — 7 routes:** `GET /api/health`, `POST /api/open`, `POST /api/recommend`, `POST /api/run`, `GET /api/intents`, and `GET /`, `GET /app` serving the frontend.
  **Deviation:** the frontend is a self-contained hand-written HTML wizard with no build step — not React as designed. This was a deliberate trade: zero toolchain, works offline, ships inside the wheel.

**Parity is enforced by three things:** (1) shared engine modules, no duplicated logic; (2) figures rendered engine-side (Principle 2); (3) a serializable `RunRecord` (Section 13). The success metric — CLI and web produce byte-identical provenance except timestamp — is asserted by `tests/integration/test_cli_web_parity.py` (11 tests).

**Two known surface defects:**
- `GET /api/intents` hardcodes the original 6 intents. The 7 SQ intents (Section 5a) are unreachable from the frontend.
- `POST /api/recommend` defaults `use_literature=False`; the engine default is `True`. A web run and a CLI run of the "same" request are not the same request unless the flag is set explicitly.

## 8. Method catalog & plugin contract  **[AS BUILT]**

A catalog entry is YAML; its `impl` and `cost_model` are dotted `module:function` paths resolved at load. Seven entries ship in `catalog/entries/`.

```yaml
# catalog/entries/permanova.yaml — the real entry
id: permanova
name: PERMANOVA (Permutational ANOVA of distances)
intents: [comparison, sq6_genomic_context, sq7_association]
sq: [sq6_genomic_context, sq7_association]     # which SQ questions this answers
requires: {presence_absence: presence_absence_matrix, grouping_col: str}
params:
  metric:       {default: braycurtis}
  permutations: {default: 999}
  correction:   {default: bh}
assumptions: [two_groups_in_metadata, min_group_n_3, group_balance_warning]
cost_model: bgclens.catalog.methods.permanova:cost
impl:       bgclens.catalog.methods.permanova:run
citation: {doi: "10.1111/j.1442-9993.2001.01070.pp.x", note: "Anderson 2001"}
```

Every `impl` module exposes three callables with a uniform signature:

```python
def run(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]
def check_assumptions(inputs, params) -> list[str]        # warnings, not exceptions
def cost(inputs, params) -> dict                          # {class, reason, estimated_mb}
```

**Note:** `cost_model` lives *alongside* each method (`catalog.methods.<m>:cost`), not in a central `compute.models` module as originally designed. `ordination.py` backs two entries (`pca`, `pcoa`) via `run_pca`/`run_pcoa` and `pca_cost`/`pcoa_cost`.

**CI validates the catalog:** `registry.validate_catalog()` asserts every entry has `id`, `name`, `intents`, `impl`, `citation`, and that `get_impl()` resolves. This is the governance backstop (Section 14).

**Coverage:** 7 methods — `fisher_enrichment`, `pca`, `pcoa`, `permanova`, `alpha_diversity`, `hierarchical_clustering`, `louvain_community`. NMDS was in the design's seed list and was **not** implemented.

## 9. Literature service + the validation rule  **[AS BUILT — expanded]**

The design specified OpenAlex with others "pluggable later". **Three providers ship**, behind a `@runtime_checkable` Protocol:

```python
class LiteratureProvider(Protocol):
    def support_for(method_terms, topic_terms, window_years=10, max_citations=5
                   ) -> list[MethodLiteratureSupport]

def get_provider(name: str | None = None) -> LiteratureProvider | None
    # name arg → BGCLENS_LITERATURE_PROVIDER env var → default "openalex"
    # unrecognised or unset → None → offline fallback in ranker.rank_methods()
```

| Provider | Backend | Role |
|---|---|---|
| `OpenAlexProvider` | `api.openalex.org/works` | default; decodes `abstract_inverted_index` |
| `EuropePMCProvider` | Europe PMC REST | alternative corpus, same co-occurrence rule |
| `MiBiGProvider` | `mibig.secondarymetabolites.org/api/v1` | maps topic terms → BGC compound classes; returns reference-cluster citations for **novelty/precedent** queries |

`ranker.merge_supports()` combines results across providers with citation dedup.

**The validation rule (the crux, unchanged):** a method is labelled "literature-supported for topic T" only if the provider returns works where the *method term co-occurs with topic terms* in title/abstract. Each surfaced citation must be a work in which **both** appear — co-occurrence, not a keyword hit on either alone. Methods below threshold are labelled **"valid, no strong literature match"** — never dropped, never given fabricated citations. Provider unreachable → literature step skipped, explicitly labelled. Queries cached 7 days.

**Support thresholds (as built):** ≥10 works → `strong`; ≥3 → `moderate`; ≥1 → `weak`; else `none`.

**Known defect:** `ranker.rank_methods()` hardcodes `provider="openalex"` in the returned `LiteratureRanking` on the success path regardless of which backend actually ran. The label is correct only on the offline fallback (`provider="offline"`). Provenance therefore records the wrong provider whenever Europe PMC or MIBiG is selected.

## 10. Compute advisor  **[AS BUILT]**

- **Resource detection:** local via `psutil` (physical cores, available RAM). Cluster detection is *read-only*: presence of `sinfo`/`squeue`. **No job submission.**
- **Cost estimation:** each method declares `cost(inputs, params) -> {class, reason, estimated_mb}` alongside its `run()`. Distance-matrix methods are O(N²) in genome count; PERMANOVA scales with permutations × N.
- **Classification:** `_HEADROOM = 0.70` — a method is `Heavy` if its estimate exceeds 70% of *available* RAM, and `Likely-to-fail` if it exceeds 90% of *total* RAM. Estimates are labelled approximate with the driving factor shown.
- **Lighter alternative (US-007):** for Heavy/Likely-to-fail, `CostAssessment.alternatives` carries ≥1 same-intent method of lower cost class with its `trade_off` string.

**Division of labour — three distinct concerns, deliberately separate:**

| Layer | Question | On failure |
|---|---|---|
| Compute advisor (§10) | Will this *fit*? | Gates (`Likely-to-fail`) |
| `check_assumptions` (§12) | Is this *valid* for the data? | Warns, never blocks |
| Validation harness (§12a) | Is the output *internally coherent*? | Bands green/amber/red |

## 11. Visualization service  **[AS BUILT]**

`viz.render(result, metadata) -> (svg_bytes, png_bytes)`. A `recommend_chart()` mapping `(result_type × intent) → chart` selects the renderer:

- ordination (PCA/PCoA) → grouped scatter
- enrichment → dot plot / volcano
- diversity → box/violin
- presence/absence → clustered heatmap
- network → node-link

Colorblind-safe palette, labelled axes, consistent theme, vector export. Because rendering is engine-side, figures are deterministic and byte-identical across surfaces.

**Not built:** the "≥1 valid alternative offered" requirement. `recommend_chart()` computes alternatives; neither surface exposes a switch. NMDS never shipped, so it is not a chart target.

## 12. Interpretation service  **[AS BUILT]**

Three-stage, deterministic-first. Stage 3 shipped (the design's `[DECIDE]` on whether to defer it resolved to *build it, behind a flag*).

1. **Facts extraction (deterministic):** `extract_facts(result, assumption_warnings) -> InterpretationFacts` — effect size, significance, direction, n, `key_numbers`, caveats, and a `what_it_does_not_tell_you` list. Dispatched per method.
2. **Template (deterministic):** `render_template(facts) -> str` — correct, if stiff, prose under `##` headers.
3. **LLM phrasing (optional):** `rephrase(template_text, facts)` — gated on `BGCLENS_LLM_ENABLED` + an API key. The LLM receives **only** the facts object and the template text. Never raw data.

**The acceptance gate.** The deployed endpoint is assumed to be a small, weak model, so goals are binary and mechanical — what a weak model *and a weak judge* can reliably be held to. A candidate must pass **all four hard goals**:

| Goal | Check |
|---|---|
| `fidelity` | No number/DOI/PMID/accession absent from `facts.key_numbers` |
| `structure` | Every `##` header from the template survives |
| `no_preamble` | Does not open with meta-commentary or a code fence |
| `substance` | Non-empty and ≥60% of template length (`MIN_LENGTH_RATIO`) |

A first failure gets **one retry with a stricter prompt** that enumerates the exact headers to reproduce. A second failure returns the template **verbatim**. Any exception anywhere returns the template verbatim. There is no path where the LLM degrades scientific accuracy.

Soft goals (`meaning_preserved`, `fluency_improved`) are graded by an LLM judge and are **advisory only** — they never gate.

**Assumption checks:** each method's `check_assumptions` runs before execution; violations become warnings shown in the recommendation and carried verbatim into interpretation caveats. They *warn*, never block.

**Multiple-testing:** correction is **ON by default (Benjamini–Hochberg FDR)**, with `correction` (`bh`/`bonferroni`/`none`) and `alpha` exposed as params. Both raw and adjusted values are stored; interpretation reports the adjusted result.

## 12a. Validation harness  **[NEW — not in original design]**

A separate, deterministic answer to "is this output internally coherent?", independent of whether the method's assumptions held.

```python
def evaluate(method_id: str, result: dict) -> ValidationResult
# ValidationResult = {method_id, checks: list[CheckResult], confidence_band}
# CheckResult     = {name, passed, detail}
# ConfidenceBand  = Literal["green", "amber", "red"]

def band(passed: int, total: int) -> ConfidenceBand
# ≥0.8 → green · ≥0.5 → amber · else red · total==0 → amber
```

A per-method registry maps method ids to check lists. Checks **never raise** — an exception becomes a failed `CheckResult`. Unknown method → zero checks → `amber`.

| Method | Checks |
|---|---|
| `pcoa`, `pca` | has coordinates; explained variance sums to 1.0 ± 0.01; coord width == n_components |
| `alpha_diversity` | has scores; scores non-negative |
| `fisher_enrichment` | has p-values; p ∈ [0,1] |
| `hierarchical_clustering`, `louvain_community` | has labels; labels are ints |
| `permanova` | has R² and p-value; both in range |

`api.run()` attaches `_confidence_band` and `_validation_checks` to every result. The harness depends on nothing outside its own package.

## 12b. Manufacturability objective  **[NEW — not in original design]**

An optional recommendation re-ranking driven by `AnalysisRequest.objective == "manufacturability"`.

```python
compute_features(project) -> TierAFeatures
    # {n_bgcs, mean_cluster_size_kb, gc_content_mean, bgc_class_counts,
    #  tractability_score, notes}

compute_profile(features) -> ManufacturabilityProfile
    # {tractability_score, n_bgcs, top_class, notes}

reorder_for_manufacturability(recommendations, profile) -> list
```

**Tractability score** is a count-weighted average of per-BGC-class heterologous-expression constants — RiPP 0.9, Terpene 0.85, NRP 0.7, NRPS 0.65, Other 0.6, Hybrid 0.55, PKS-other 0.5, PKS-II 0.45, PKS-I 0.4 (default 0.5). The ordering encodes "PKS-I hardest, RiPPs easiest".

**Reorder policy** — a stable partition, not a re-scoring:
- score ≥ 0.7 → boost `{fisher_enrichment, diversity}` (exploit: the clusters are expressible, go find *which* ones)
- score < 0.5 → boost `{pcoa, pca, clustering}` (explore: characterise diversity before committing bench time)
- 0.5 ≤ score < 0.7 → unchanged

**Caveats, stated plainly:** the constants are a literature-informed heuristic, not a fitted model, and are not individually cited. `TierAFeatures.mean_cluster_size_kb` is declared but never populated. `compute_features` never raises; failures land in `notes`. This module is the least scientifically grounded part of the system and should be treated as a prioritisation hint, not evidence.

## 13. Provenance & config format  **[AS BUILT]**

One artifact serves three jobs — reproduce, document, and transfer between surfaces:

```yaml
bgclens_run:
  project_path: /data/processed/mq_saccharopolyspora
  inputs_hash:  sha256:...          # path + mtimes of up to 20 CSVs
  request:      {topic: ..., intent: comparison}
  run_spec:     {method_id: permanova, params: {permutations: 999, correction: bh}}
  literature:   {provider: openalex, ...}     # see §9 known defect
  llm:          {enabled: true, used: true}   # API key NEVER written
  result_summary: {...}
  created_at:   <timestamp>
```

`RunRecord.save()` writes `bgclens_run_{inputs_hash[:8]}.yaml` beside outputs on every run. `from_yaml()` reads it back. Parity — identical provenance except `created_at` from either surface — is asserted by `test_cli_web_parity.py`.

**Not built:** the round-trip. No surface *loads* a `RunRecord` to replay a run. The CLI `run` command takes `--method` and `--params`, not `--config`. `RunRecord` is currently an export and audit format, not an input format. Closing this is the single highest-value gap in the reproducibility story.

## 13a. Report renderer  **[NEW — Quarto, not MkDocs]**

`report.render(run_record, out_dir) -> QuartoReport`, exposed as `bgclens report <run_id>`.

Writes `{method_id}_{method_hash}.qmd` (Quarto `params:`, `freeze: auto`), then shells out to `quarto render` for HTML if the binary is on PATH. Degrades to `.qmd`-only otherwise. **Documented never to raise** — on any error it writes `report_error.qmd` and returns a `QuartoReport` with `rendered=False` and a `note`.

The `.qmd` embeds: a **firewall badge** (`precedent` if the run carried literature support, else `deterministic`), the figure (inline SVG, or PNG as a base64 `data:` URI), the interpretation, and a `## Provenance` JSON block. `method_hash` is `sha256(provenance)[:12]`, emitted as an HTML comment.

**Deviation:** the design (and PRD US-014) specified MkDocs pages compatible with `bgcflow serve`. Quarto was chosen instead. MkDocs compatibility is unbuilt.

## 14. Catalog governance

Catalog entries live in-repo as YAML. Adding/changing one is a pull request that must link a tested `impl`, declare a `cost_model` and `check_assumptions`, and carry a real citation. `registry.validate_catalog()` rejects entries failing any of these and runs in CI.

**Unresolved.** The design called for a designated maintainer with natural-products / biostatistics knowledge as required reviewer on catalog PRs. **No such reviewer has been named.** CI checks *structure* — that a citation field exists and an `impl` resolves — not *scientific correctness*. A wrong statistic with a confident interpretation remains this product's worst failure mode, and the gate that was supposed to catch it does not exist yet.

## 15. Tech stack & repository layout  **[AS BUILT]**

Python throughout. Methods lean on citable libraries: `scipy`, `scikit-learn`, `statsmodels`, `networkx` (`scikit-bio` is an optional extra). Web API `FastAPI`; CLI `Typer`; figures `matplotlib`. **Frontend is hand-written self-contained HTML, not React** — no build step, works offline, ships inside the wheel.

```
bgclens/                 # the engine — the product
  model/                 # canonical types (§5)
  adapters/              # detect.py, duckdb_adapter.py, csv_adapter.py
  catalog/
    entries/*.yaml       # 7 method declarations (data)
    methods/*.py         # 6 implementation modules
    registry.py          # glob-load + validate_catalog()
  literature/
    provider.py          # Protocol + Citation/MethodLiteratureSupport dataclasses
    providers/           # openalex.py, europepmc.py, mibig.py + get_provider()
    openalex.py          # back-compat shim → providers.openalex
    ranker.py, cache.py
  compute/               # advisor.py, cost_models.py, resources.py (§10)
  viz/                   # recommend.py, render.py, theme.py (§11)
  interpret/             # facts, templates, llm, guard, goals, judge (§12)
  validation/            # harness.py, bands.py, tests/*.py     ← NEW (§12a)
  manufacturability/     # features.py, profile.py              ← NEW (§12b)
  report/                # quarto.py                            ← NEW (§13a)
  core/                  # api.py, intent.py, provenance.py, session.py, config.py
bgclens_cli/             # thin Typer CLI (open/recommend/run/report/web)
bgclens_web/
  api/main.py            # thin FastAPI, 7 routes
  frontend/index.html    # self-contained wizard, no build step
tests/
  fixtures/demo_project/ # synthetic 8-genome demo
  unit/                  # 14 modules
  integration/           # walking skeleton, cli↔web parity, web api, llm goals, bgcflow e2e
```

**Test suite: 176 passing, 15 skipped** (LLM- and network-gated).

## 16. Resolved decisions

Every `[DECIDE]` from the original design has been settled by the implementation. One remains genuinely open.

| PRD Open Question | Decision as built | Status |
|---|---|---|
| Interpretation: template vs LLM | Template-first deterministic; LLM phrasing shipped behind `BGCLENS_LLM_ENABLED`, gated on 4 hard goals with one strict retry and verbatim fallback | **Resolved** — built |
| Literature hallucination guard | Method+topic **co-occurrence** threshold; citations must contain both; below-threshold labelled not dropped; never fabricate | **Resolved** — firm |
| Compute detection scope | Local `psutil` + read-only `sinfo`; no job submission; 70% RAM headroom | **Resolved** — firm |
| Statistical assumption safety net | Three-layer split: advisor *gates* feasibility, `check_assumptions` *warns* on validity, validation harness *bands* coherence | **Resolved** — extended beyond design |
| Catalog ownership | In-repo YAML + CI structural validation | **⚠ Half-resolved** — no domain reviewer named; CI checks structure, not correctness |
| Multiple-testing correction | On by default (BH FDR), params exposed, raw+adjusted stored, adjusted reported | **Resolved** — firm |
| Name | **BGCLens** | **Resolved** — final |

**Decisions taken during implementation that the design did not anticipate:**

| Decision | Rationale |
|---|---|
| Frontend is plain HTML, not React | No build step; ships in the wheel; works fully offline |
| Report renderer is Quarto, not MkDocs | Better figure/provenance embedding; `.qmd` degrades gracefully without the binary |
| `visualize()`/`interpret()` stayed out of `core.api` | Emergent, not chosen — see §6. Needs ratifying or reverting |
| Intent space grew 6 → 13 (SQ framing) | Researchers pick by question, not by statistical family |
| Validation harness added (§12a) | `check_assumptions` answers validity, not output coherence. Different question, different layer |
| Manufacturability objective added (§12b) | Domain-driven prioritisation. Least grounded module in the system |

## 17. Post-build risk register

The design's pre-build spike list has been superseded. The three spikes were all executed; here is where the system actually stands.

**Spikes, resolved:**
1. **Literature validation rule** — built and unit-tested against recorded provider responses. The co-occurrence rule holds. ✅
2. **Compute cost estimation** — built with a 70% headroom margin. **Never validated against a real OOM corpus** — the ≥95% catch-rate success metric is unmeasured. ⚠
3. **Walking skeleton** — built and green (`test_walking_skeleton.py`). ✅

**Live risks, in order:**

1. **No scientific reviewer on the catalog (§14).** A wrong statistic delivered with a confident interpretation is the worst failure this tool can produce, and nothing currently prevents it. CI validates that a citation *exists*, not that the method is *correctly implemented for the claim it makes*. **This is the top risk and it is organisational, not technical.**
2. **Manufacturability constants are unfitted (§12b).** They reorder what a researcher sees, on the strength of nine hand-set numbers with no citation each. Either cite them per-class or label the feature explicitly experimental in the UI.
3. **Provider mislabelling in provenance (§9).** Runs using Europe PMC or MIBiG record `provider: openalex`. Provenance that lies is worse than provenance that is absent.
4. **The reproducibility round-trip is one flag short (§13).** `RunRecord` exports but never imports. The headline claim — "a collaborator replays your run" — is not yet true from either surface.
5. **Cost gating is unvalidated (spike 2).** We gate on estimates nobody has checked against a real failure.

**Recommended next actions,** in the order they buy the most:
1. Name a catalog reviewer. Zero code.
2. Add `bgclens run --config <RunRecord.yaml>`. Closes §13 and completes US-012.
3. Fix `ranker.rank_methods()` to report the provider that actually ran.
4. Add run history to the web session — unblocks US-009 retention and US-013.
5. Refresh `GET /api/intents` from the `Intent` enum so SQ intents reach the frontend.

## 18. Traceability to the PRD

| Design § | PRD stories | PRD requirements | Status |
|---|---|---|---|
| §3 Intent capture | US-003 | FR-3 | ✅ |
| §5 Canonical model | US-001, US-002 | FR-1, FR-2 | ✅ |
| §5a SQ intents | US-016 | FR-14 | ✅ *(web endpoint stale)* |
| §6 Engine contracts | US-008, US-009 | FR-8, FR-9 | ◐ *3 of 5 fns; no run retention* |
| §7 CLI/web parity | US-012 | FR-12 | ◐ *config import missing* |
| §8 Method catalog | US-004, US-015 | FR-4 | ✅ *(plugin iface undocumented)* |
| §9 Literature service | US-005 | FR-5 | ✅ *(provider mislabelled)* |
| §10 Compute advisor | US-006, US-007 | FR-6, FR-7 | ✅ *(gating unvalidated)* |
| §11 Visualization | US-010 | FR-10 | ◐ *alternatives not exposed* |
| §12 Interpretation | US-011 | FR-11 | ✅ |
| §12a Validation harness | US-017 | FR-13 | ✅ |
| §12b Manufacturability | US-018 | FR-15 | ✅ *(heuristic, unfitted)* |
| §13 Provenance | US-012 | FR-8 | ◐ *export only* |
| §13a Report renderer | US-014, US-019 | FR-16 | ◐ *Quarto, not MkDocs* |
| §14 Catalog governance | — | FR-4 | ⚠ *no named reviewer* |
| — | US-013 multi-run dashboard | — | ○ *blocked on §6 retention* |
