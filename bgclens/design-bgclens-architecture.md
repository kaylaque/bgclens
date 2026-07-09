# Architecture & Design: BGCLens

> Companion to `prd-bgcflow-postprocessing-layer.md`. The PRD defines *what* and *why*; this document defines *how the pieces fit*, fixes the contracts everything else depends on, and resolves the PRD's Open Questions into decisions you can react to. Working name **BGCLens** is still provisional.

## 1. Purpose of this document

The PRD is a spec, not an architecture. Three things must exist before implementation is safe: (a) the data contracts that are the spine of every feature, (b) the engine↔UI boundary that makes CLI/web parity real rather than aspirational, and (c) resolutions to the architectural forks buried in the PRD's Open Questions. This document supplies all three. Where a decision is a recommendation you should confirm, it's marked **[DECIDE]**.

## 2. Design principles (load-bearing decisions)

These are the decisions everything else hangs off. Get them wrong and the rework is expensive.

1. **The engine is the product; the CLI and web app are thin skins.** All logic — ingestion, method selection, execution, figure rendering, interpretation — lives in one importable Python library. The CLI and web API call the *same functions*. Neither surface contains analysis logic. This is the only way the "CLI run == web run" success metric is achievable.

2. **Figures are rendered in the engine, not the browser.** Rendering uses matplotlib inside the engine and emits SVG+PNG bytes. The web frontend *displays* those bytes; it does not re-plot. Consequence: a CLI run and a web run produce byte-identical figures, and figure code is testable without a browser. (Trade-off: no live client-side interactivity in MVP figures — acceptable, and revisited in Phase 2.)

3. **Science is deterministic; the LLM only touches prose.** Every number, statistic, and claim is computed by tested code. The LLM, where used, rephrases already-correct template text and is never given raw data or allowed to introduce a number. This makes the tool defensible and the interpretation layer unit-testable.

4. **The method catalog is data, not code.** Methods are declared in YAML and resolve to registered implementations. Adding a method is a data + plugin change, never an engine change. This is what makes "swap methods easily" tractable.

5. **Read-only, strictly downstream.** BGCLens never invokes or mutates BGCFlow. It only reads a finished project's outputs.

6. **Provenance is not optional.** Every run writes a complete, replayable record. Provenance *is* the config-export format — the same artifact reproduces a run and documents it.

## 3. System context

```
  ┌────────────┐      finished project (read-only)      ┌────────────────────────────┐
  │  BGCFlow    │ ───────────────────────────────────▶  │          BGCLens            │
  │  run +      │   data/processed/<project>/            │                             │
  │  build report│  ├─ DuckDB OLAP db                    │  engine (library)           │
  └────────────┘   └─ CSV/TSV summary tables             │   ├─ adapters (ingest)      │
                                                          │   ├─ canonical model        │
        ┌──────────────────┐   scholarly queries          │   ├─ catalog + methods      │
        │  OpenAlex (MCP)  │ ◀───────────────────────────▶│   ├─ literature service     │
        │  (pluggable)     │   cited, ranked methods       │   ├─ compute advisor        │
        └──────────────────┘                               │   ├─ viz (matplotlib)       │
                                                            │   ├─ interpret              │
        ┌──────────────────┐   cores / RAM / sinfo          │   └─ provenance             │
        │  local machine / │ ◀───────────────────────────  │                             │
        │  SLURM (read)    │                                │  surfaces (thin):           │
        └──────────────────┘                                │   ├─ CLI (Typer)           │
                                                            │   └─ Web API (FastAPI)+UI   │
                                                            └────────────────────────────┘
```

## 4. Layered architecture

Eight components inside the engine, plus two surfaces. Data flows downward; provenance is cross-cutting.

1. **Adapters** — read BGCFlow output (DuckDB first, CSV/TSV fallback), detect which pipelines ran, emit a **ProjectManifest**.
2. **Canonical model** — normalize heterogeneous outputs into a small fixed set of types joined on `genome_id` (Section 5).
3. **Method catalog** — versioned YAML registry of methods + their registered implementations, constraints, cost models, citations (Section 8).
4. **Literature service** — MCP abstraction that ranks candidate methods by literature support for the topic and attaches real citations (Section 9).
5. **Compute advisor** — estimates cost, detects resources, classifies Safe/Heavy/Likely-to-fail, recommends lighter alternatives (Section 10).
6. **Analysis engine** — the orchestrator that ties the above into the request→recommend→run flow (Section 6).
7. **Visualization service** — result→recommended chart→rendered SVG+PNG (Section 11).
8. **Interpretation service** — computed result→grounded facts→narrative with caveats + citations (Section 12).

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

**First build target:** these types + the BiG-SCAPE adapters + a loader test against the public `mq_saccharopolyspora` demo. This is the walking skeleton's foundation.

## 6. Core engine contracts

The engine exposes a small, stable API that both surfaces call. This *is* the parity mechanism.

```python
def open_project(path: Path) -> Project                      # ingest + manifest (US-001/002)

def recommend(project, request: AnalysisRequest) -> list[MethodRecommendation]
    # intent → valid candidates (catalog) → literature rank (§9) → cost class (§10)

def run(project, spec: RunSpec) -> AnalysisResult            # execute approved method (US-008)
def visualize(result: AnalysisResult) -> list[VizSpec]       # recommend + render (US-010)
def interpret(result, viz: VizSpec) -> Interpretation        # grounded narrative (US-011)

# Value objects
AnalysisRequest = {topic: str, intent: Intent, method_hint: str|None}
MethodRecommendation = {method_id, validity, assumption_warnings,
                        literature: LiteratureSupport, cost: CostClass, is_recommended}
RunSpec = {method_id, params: dict}          # the unit of reproducibility
AnalysisResult = {stats, params, inputs_hash, provenance, warnings}
RunRecord = AnalysisResult + VizSpec + Interpretation   # persisted bundle
```

Flow for one analysis: `open_project → recommend → (user/config picks) → run → visualize → interpret → persist RunRecord`. **Method swap (US-009)** re-enters at `recommend`/`run` with the same loaded `Project`, retaining prior `RunRecord`s in the session for comparison — no disk re-read.

## 7. Engine↔UI boundary & CLI/web parity

Both surfaces are thin translators between user input and the engine API.

- **CLI (Typer):** subcommands mirror the engine — `bgclens open`, `recommend`, `run`, `report`. Non-interactive mode takes a config file and runs the whole flow. Interactive mode prompts through the same stages.
- **Web (FastAPI + React):** the API layer is a 1:1 HTTP wrapper over the engine functions; endpoints return the same value objects as JSON, plus figure bytes. React renders the wizard (ingest → ask → recommend → run → view → interpret) and *displays* engine-produced SVGs.

**Parity is enforced by three things:** (1) shared engine, no duplicated logic; (2) figures rendered engine-side (Principle 2); (3) a single serializable `RunSpec`+project reference (Section 13) that either surface can export and the other can replay. The success metric — CLI and web produce byte-identical provenance except timestamp — is testable in CI by running the same config through both paths.

## 8. Method catalog & plugin contract

A catalog entry is YAML; its `impl` points to a registered callable.

```yaml
id: permanova
name: PERMANOVA
intents: [comparison]
requires: {distance_matrix_from: presence_absence}
impl: bgclens.catalog.methods.permanova:run
params: {permutations: {default: 999}, correction: {default: bh}}
assumptions: [group_balance, min_group_n>=3]
cost_model: bgclens.compute.models:permanova_cost   # dims → cost
citation: {doi: 10.xxxx, note: "Anderson 2001"}
```

The plugin interface every `impl` implements:

```python
def run(inputs: CanonicalInput, params: dict) -> MethodOutput
def check_assumptions(inputs, params) -> list[AssumptionWarning]
def cost(inputs, params) -> CostEstimate      # drives §10
```

**CI validates the catalog:** every entry resolves to a real callable, declares a citation, and has a cost model and assumption check. This is the governance backstop (Section 14).

## 9. Literature service + the validation rule  [resolves OQ2]

Interface behind which OpenAlex sits (Europe PMC / Semantic Scholar pluggable later):

```python
class LiteratureProvider(Protocol):
    def support_for(method_terms, topic_terms, window_years) -> LiteratureSupport
```

**The validation rule (the crux):** a method is labelled **"literature-supported for topic T"** only if the provider returns works where the *method term co-occurs with topic terms* in title/abstract/concepts, above a minimum count within a recency window. Each surfaced citation must be a work in which **both** the method and a topic concept appear — co-occurrence, not mere keyword hit on either alone. Methods below threshold are labelled **"valid, no strong literature match"** — never dropped, never given fabricated citations. If the provider is unreachable, the literature step is skipped and catalog defaults are shown, explicitly labelled as such. All queries are cached and rate-limited.

This keeps the layer honest: it ranks and cites *retrieved* evidence; it never asserts usage it cannot show.

## 10. Compute advisor  [resolves OQ3]

- **Resource detection (MVP):** local via `psutil` (physical cores, available RAM). Cluster detection is *read-only*: presence of `sinfo`/`squeue`, and parse `sinfo` for max node RAM. **No job submission in MVP.**
- **Cost estimation:** each method declares a `cost_model(dims) → CostEstimate` giving dominant term (time and peak memory) as a function of input size — e.g. distance-matrix methods are O(N²) memory in genome count; PERMANOVA scales with permutations × N.
- **Classification:** compare estimate against detected resources with a headroom margin → **Safe** / **Heavy (warn)** / **Likely-to-fail (gate)**. Estimates are always labelled approximate, with the driving factor shown ("dominated by N=2,400 pairwise distances").
- **Lighter alternative (US-007):** for Heavy/Likely-to-fail, recommend ≥1 same-intent catalog method of lower cost class, stating the trade-off (e.g. PCoA on a subsample loses some resolution; approximate community detection trades exactness for speed).

Note the division of labour: the compute advisor gates on *feasibility*; assumption checks (Section 12) warn on *validity*. They're separate concerns.

## 11. Visualization service

A mapping `(result_type × intent) → recommended chart`, rendered with matplotlib to SVG+PNG:

- ordination (PCA/PCoA/NMDS) → grouped scatter
- enrichment → dot plot / volcano
- diversity → box/violin + rarefaction curve
- presence/absence → clustered heatmap
- network → node-link or adjacency matrix

Requirements baked into the renderer: colorblind-safe palette, labelled axes with units, readable type, consistent theme, ≥1 valid alternative offered, vector export. Because rendering is engine-side, figures are deterministic and identical across surfaces.

## 12. Interpretation service  [resolves OQ1, OQ4, OQ6]

Three-stage, deterministic-first:

1. **Facts extraction (deterministic):** pull a structured `InterpretationFacts` object *from the result numbers only* — effect size, significance, direction, n, and which assumption/multiple-testing flags fired.
2. **Template (deterministic):** turn facts into correct, if stiff, prose: what was tested, result in plain language, effect in context, caveats, and a "what this does NOT tell you" section.
3. **LLM phrasing (optional, constrained):** rephrase the *template output* for fluency. The LLM receives only the facts object + template text — never raw data — and its output is validated to introduce no number absent from the facts. **[DECIDE]** MVP can ship stage 1–2 only and add stage 3 behind a flag.

**Assumption checks [OQ4]:** each method's `check_assumptions` runs before execution; violations become warnings shown in the recommendation and carried verbatim into the interpretation caveats (e.g. unbalanced groups for PERMANOVA). These *warn*, they don't block — blocking is reserved for cases the compute advisor flags as mathematically failing.

**Multiple-testing [OQ6]:** for enrichment/multi-hypothesis methods, correction is **ON by default (Benjamini-Hochberg FDR)**, with method and alpha exposed as params; both raw and adjusted values are stored, and interpretation always reports the adjusted result.

## 13. Provenance & config format  [the parity + reproducibility backbone]

One artifact serves three jobs — reproduce, document, and transfer between surfaces:

```yaml
bgclens_run:
  project: {path: ..., inputs_hash: sha256:...}
  request: {topic: ..., intent: comparison}
  run_spec: {method_id: permanova, params: {permutations: 999, correction: bh}}
  environment: {bgclens_version, python, key_lib_versions}
  literature: {provider: openalex, query_hash, cached_at}
  result_summary: {key_stats...}
  created_at: <timestamp>
```

Written to disk beside outputs on every run. A CLI run exports this; the web app imports it (and vice versa). The success metric — identical provenance except `created_at` from either surface on the same config — is a CI test.

## 14. Catalog governance  [resolves OQ5]

Catalog entries live in-repo as YAML. Adding/changing one is a pull request that must: link a tested `impl`, declare a `cost_model` and `check_assumptions`, and carry a real citation. CI rejects entries failing any of these. **[DECIDE]** designate a maintainer with domain (natural-products / biostatistics) knowledge as required reviewer for catalog PRs — a wrong statistic with a confident interpretation is this product's worst failure mode, so this review gate is not optional.

## 15. Tech stack & repository layout

Python throughout (ecosystem match with BGCFlow; stats libraries live here). Methods lean on citable libraries: `scipy`, `scikit-bio`, `scikit-learn`, `statsmodels`, `networkx`. Web API `FastAPI`; CLI `Typer`; frontend `React`. Figures `matplotlib`. Packaged for conda/mamba on Linux (BGCFlow's baseline).

```
bgclens/                 # the engine — the product
  model/                 # canonical types (§5)   ← build first
  adapters/              # BGCFlow ingestion (duckdb, csv)
  catalog/
    entries/*.yaml       # method declarations (data)
    methods/*.py         # registered implementations
    registry.py
  literature/            # provider protocol + openalex client (§9)
  compute/               # cost models + resource detection + advisor (§10)
  viz/                   # recommendation + matplotlib renderers (§11)
  interpret/             # facts + templates + optional llm phrasing (§12)
  core/                  # engine API, session, provenance (§6,§13)
bgclens_cli/             # thin Typer CLI
bgclens_web/
  api/                   # thin FastAPI over core
  frontend/              # React wizard (displays engine figures)
tests/
  data/                  # public mq_saccharopolyspora demo fixtures
```

## 16. Resolved decisions (react to these)

| PRD Open Question | Decision | Confidence |
|---|---|---|
| Interpretation: template vs LLM | Template-first deterministic; LLM phrasing optional, constrained, behind a flag | **[DECIDE]** — recommended |
| Literature hallucination guard | Method+topic **co-occurrence** threshold; citations must contain both; below-threshold labelled not dropped; never fabricate | Firm |
| Compute detection scope | Local `psutil` + read-only `sinfo`; no job submission in MVP | Firm |
| Statistical assumption safety net | Per-method `check_assumptions`, warn (not block) except mathematical failure | Firm |
| Catalog ownership | In-repo YAML + CI validation + designated domain reviewer on PRs | **[DECIDE]** — needs a named owner |
| Multiple-testing correction | On by default (BH FDR), params exposed, raw+adjusted stored, adjusted reported | Firm |
| Name | "BGCLens" provisional | Open |

## 17. What to spike before committing to the full build

In risk order — these are where "fine in the doc" and "actually works" diverge most:

1. **Literature validation rule (Section 9)** against real OpenAlex responses for 2–3 real topics. Confirm the co-occurrence threshold produces sane rankings and defensible citations. If this can't be made trustworthy, the whole literature pillar is in question — know that first.
2. **Compute cost estimation (Section 10)** on the demo dataset — do the O(N²)/permutation estimates actually predict real time/memory closely enough to gate on?
3. **Walking skeleton:** demo project → one hardcoded method (e.g. PCoA) → one figure → one templated interpretation, wired through the *real* engine API. This proves the Section 5/6 contracts before 12 stories are built on them.

## 18. Traceability to the PRD

Section 5 ⇒ US-001/002, FR-1/2. Section 6 ⇒ US-008/009, FR-8/9. Section 7 ⇒ US-012, FR-12. Section 8 ⇒ US-004, FR-4. Section 9 ⇒ US-005, FR-5. Section 10 ⇒ US-006/007, FR-6/7. Section 11 ⇒ US-010, FR-10. Section 12 ⇒ US-011, FR-11. Section 13 ⇒ US-012, FR-8. Section 3 ⇒ US-003, FR-3.
