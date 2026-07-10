# PRD: BGCLens — Post-Processing & Interpretation Layer for BGCFlow

> **BGCLens** — a downstream companion to BGCFlow that turns raw pipeline output into interpretable, method-flexible, literature-grounded, publication-ready results.
>
> **Status: MVP implemented.** Last reconciled against the codebase 2026-07-10. Test suite: **176 passing, 15 skipped** (LLM- and network-gated). Statuses below are marked ✅ done · ◐ partial · ○ not started, and reflect what the code actually does — not what was planned.

## Implementation status at a glance

| Area | Status | Notes |
|---|---|---|
| Ingest + canonical model (US-001/002) | ✅ | 6 canonical types; DuckDB → CSV fallback |
| Intent capture (US-003) | ✅ | Expanded 6 → **13 intents** (adds SQ1–SQ7) |
| Method catalog (US-004) | ✅ | 7 entries, YAML-driven, CI-validated |
| Literature ranking (US-005) | ✅ | **3 providers**: OpenAlex, Europe PMC, MIBiG |
| Compute advisor (US-006/007) | ✅ | Safe / Heavy / Likely-to-fail + alternatives |
| Run + provenance (US-008) | ✅ | Adds confidence bands + validation checks |
| Method swapping (US-009) | ◐ | Swap works; **multi-run retention not built** |
| Visualization (US-010) | ◐ | SVG+PNG render; alternative chart switching not exposed |
| Interpretation (US-011) | ✅ | Facts → template → guarded LLM, 4 hard goals |
| Shared engine, CLI + web (US-012) | ◐ | Parity tested; **config-file run not built** |
| Multi-run comparison (US-013, Ph2) | ○ | |
| Report bundle export (US-014, Ph2) | ◐ | **Quarto** `.qmd`/HTML shipped (not MkDocs) |
| Method plugins (US-015, Ph3) | ○ | Catalog is pluggable; interface undocumented |

**Built beyond the original spec** — see US-016 through US-019: scientific-question intents, a deterministic validation harness with confidence bands, a manufacturability re-ranking objective, and Quarto report rendering.

## Introduction / Overview

BGCFlow produces excellent raw output — antiSMASH BGC tables, BiG-SCAPE GCF networks and presence/absence matrices, CheckM/GTDB-Tk quality and taxonomy, ARTS/GECCO results, and a DuckDB OLAP database. But two recurring problems block researchers from getting value out of it:

1. **Interpretation gap.** Many users (especially wet-lab biologists) can generate the tables but struggle to understand what the numbers *mean* scientifically.
2. **Rigid post-processing.** The statistical treatment and visualization baked into BGCFlow's report notebooks are fixed starting points. Swapping in a different statistical approach, or choosing a visualization that matches the research question, currently means hand-editing notebooks — which most users never revisit.

**BGCLens** sits *downstream* of BGCFlow (`bgcflow run` → `bgcflow build report` → **BGCLens**). It ingests a completed BGCFlow project, lets the user state a research question, gathers the statistical/post-processing methods the literature actually uses for that kind of analysis (via a scholarly MCP such as OpenAlex), lets them swap between those methods trivially, checks whether their machine can run the chosen method, renders a scientifically-defensible visualization, and writes a plain-language interpretation with caveats and citations.

It ships as **both a web app** (for the mixed lab, especially non-coders) **and a CLI tool** (for bioinformaticians who want reproducibility and batch runs). Both drive the same underlying analysis engine.

**Scope note:** The four capabilities (interpret, swap methods, literature-ground, visualize) are large as one product. This PRD defines an **MVP core** plus explicit **Phase 2/3** boundaries so the first release is shippable and coherent.

## Goals

- Let a user point BGCLens at a finished BGCFlow project and get an interpretable result without editing any code.
- Present, for a stated research topic, a menu of statistical/post-processing methods grounded in what the literature actually uses — each with citations.
- Make swapping between methods a one-action change that re-runs analysis + viz + interpretation on the same input.
- Before running any method, estimate its compute cost, detect available resources, and either warn/gate or recommend a lighter alternative.
- Auto-select and render a scientifically-defensible, publication-quality visualization appropriate to the data + method.
- Produce a plain-language interpretation that is accurate, appropriately caveated, and cites both the methods and the source data.
- Serve identical analysis capability through a GUI and a CLI, from a shared engine.

## Non-Goals (Out of Scope)

- **Not** a replacement for BGCFlow. BGCLens never runs antiSMASH/BiG-SCAPE/etc. — it only post-processes existing BGCFlow output.
- **Not** a genome/BGC *detection* tool. No new BGC calling, no re-annotation.
- **Not** a general-purpose stats platform. The method catalog is scoped to analyses meaningful for BGC/pangenome output (enrichment, ordination, diversity, clustering, network community detection, comparative presence/absence).
- **Not** an LLM that invents statistics. Every offered method is from a curated, validated catalog; the literature layer *ranks and cites*, it does not fabricate methods. (See Open Questions on hallucination guardrails.)
- **No** cloud compute provisioning in MVP — compute checks are about the user's *existing* machine/cluster, not spinning up new resources.
- **No** manuscript auto-writing. Interpretation produces a results/figure explanation, not a full paper.
- **No** editing of BGCFlow's own config or re-triggering its pipelines.

## Target Users

Mixed lab, two primary personas:

- **Bianca (wet-lab biologist):** Can run BGCFlow with help, cannot code confidently. Lives in the web app. Needs guidance, defaults, plain-language output.
- **Dev (bioinformatician):** Comfortable with CLI, wants reproducibility, config-as-code, batch runs, and the ability to export/extend. Lives in the CLI, occasionally the web app for figures.

Both must reach the same analytical result; the CLI is not a second-class citizen.

## User Stories

Stories are ordered as vertical slices. **MVP = US-001 through US-012.** Phase 2 = US-013+. Each is small enough for one focused implementation session.

### US-001: Ingest a BGCFlow project and detect what ran ✅
**Description:** As a user, I want BGCLens to read a finished BGCFlow project directory so it knows which analyses are available to post-process.

**Acceptance Criteria:**
- [x] Accept a path to a BGCFlow `data/processed/<project>` directory (and/or its DuckDB file)
- [x] Detect which pipelines produced output (antismash, bigscape, bigslice, gecco, checkm, gtdbtk, arts, roary/pangenome, mash/fastani)
- [x] Return a structured "capabilities manifest" listing available datasets and their shapes (e.g. GCF presence/absence matrix: N genomes × M GCFs)
- [x] Fail gracefully with a clear message if the path is not a valid BGCFlow project
- [x] Typecheck/lint passes

**As built:** `adapters/detect.py` → `ProjectManifest`. Detection is filename-presence based; no config file required. Surfaced by `bgclens open`.

### US-002: Load core result tables into a normalized in-memory model ✅
**Description:** As a developer, I need BGCFlow's heterogeneous outputs mapped into a small set of canonical data structures so downstream methods don't care which tool produced them.

**Acceptance Criteria:**
- [x] Define canonical types: `PresenceAbsenceMatrix`, `FeatureCountTable`, `TaxonomyTable`, `QualityTable`, `NetworkEdgeList`, `MetadataTable`
- [x] Load BiG-SCAPE GCF presence/absence, BGC-per-genome counts, and MIBiG-known-cluster tables into these types
- [x] Load genome metadata (taxonomy, quality) and join on `genome_id`
- [x] Read from DuckDB when present, fall back to CSV/TSV files
- [x] Unit tests cover at least one real BGCFlow demo dataset (e.g. the public `mq_saccharopolyspora` demo)
- [x] Typecheck passes

**As built:** all six types are pydantic models in `model/`. Adapters: `duckdb_adapter.py`, `csv_adapter.py`.

### US-003: Capture the research question / topic ✅
**Description:** As a user, I want to state what I'm actually asking (e.g. "which BGC classes are enriched in one clade vs another?") so BGCLens can recommend relevant methods.

**Acceptance Criteria:**
- [x] Free-text topic input plus a structured "analysis intent" picker (enrichment / diversity / ordination / clustering / comparison / network structure)
- [x] Map the intent to the subset of the method catalog that is valid for the available data (from US-001 manifest)
- [x] If the intent is incompatible with available data, explain why and suggest what BGCFlow pipeline would need to have run
- [x] Typecheck passes
- [ ] Verify in browser using dev-browser skill

**As built:** the intent space grew from 6 to **13** — see US-016. Incompatibility raises `MissingRequirementError` naming the BGCFlow tool to run. **Known gap:** the web `GET /api/intents` endpoint still hardcodes only the original 6 intents; the 7 SQ intents are not reachable from the frontend.

### US-004: Curated method catalog (seed) ✅
**Description:** As a developer, I need a validated, versioned catalog of post-processing methods so every offered option is real and correctly implemented.

**Acceptance Criteria:**
- [x] Catalog entries include: id, name, analysis intent(s), required input type, output type, implementation reference (library + function), assumptions/constraints, and a canonical citation
- [x] Seed with: Fisher's exact enrichment; PCA and PCoA; PERMANOVA; hierarchical clustering; Shannon & Simpson diversity; Louvain network community detection
- [x] Each entry maps to a concrete, tested implementation (scipy/scikit-learn/networkx)
- [x] Catalog is data (YAML/JSON), not hardcoded, so it can grow without code changes
- [x] Typecheck passes

**As built:** **7 entries** in `catalog/entries/*.yaml`, 6 implementation modules (`ordination.py` backs both `pca` and `pcoa`). `registry.validate_catalog()` is the CI gate. **Deviation:** NMDS was specified in the seed list but not implemented — PCoA and PCA cover the ordination intent.

### US-005: Literature-grounded method ranking via scholarly MCP ✅
**Description:** As a user, I want BGCLens to tell me which of the valid methods the literature actually uses for my topic, with citations, so my choice is defensible.

**Acceptance Criteria:**
- [x] Integrate a scholarly provider (OpenAlex primary; pluggable so Europe PMC / others can be added)
- [x] Given the topic + candidate methods, query the provider and surface: which methods appear in the corpus, rough frequency, and 2–5 representative citations per method
- [x] Rank catalog methods by literature support for this topic; clearly separate "commonly used in this area" from "valid but rarely used here"
- [x] Every surfaced claim links to a real source; if the provider returns nothing, say so and fall back to catalog defaults (never fabricate citations)
- [x] Cache/rate-limit calls; degrade gracefully when offline
- [x] Typecheck passes
- [ ] Verify in browser using dev-browser skill

**As built:** three providers behind the `LiteratureProvider` protocol — **OpenAlex**, **Europe PMC**, and **MIBiG** (the last returns reference-cluster citations for novelty/precedent queries). Selected via `get_provider(name)` or the `BGCLENS_LITERATURE_PROVIDER` env var; unknown/unset → `None` → offline fallback. Support levels: ≥10 strong, ≥3 moderate, ≥1 weak, else none. 7-day cache. `merge_supports()` combines multiple providers.

**Known defect:** `ranker.rank_methods()` hardcodes `provider="openalex"` in the returned `LiteratureRanking` on the success path regardless of which backend actually ran. The label is only accurate for the offline fallback.

### US-006: Compute-cost estimation for a candidate method ✅
**Description:** As a user, I want to know whether a method will actually run on my machine before I start it.

**Acceptance Criteria:**
- [x] Estimate cost from input dimensions × method complexity class
- [x] Detect available resources (CPU cores, RAM; detect if on a known scheduler like SLURM)
- [x] Classify each candidate method as: Safe / Heavy (warn) / Likely-to-fail (gate) for this dataset on this machine
- [x] Estimates are labeled as approximate, with the driving factor shown
- [x] Typecheck passes

**As built:** `compute/advisor.py` with a 70% RAM headroom margin; each catalog entry declares its own `cost_model`.

### US-007: Lighter-alternative recommendation ✅
**Description:** As a resource-constrained user, I want BGCLens to suggest a cheaper method that answers the same question when my first choice is too heavy.

**Acceptance Criteria:**
- [x] For a gated/heavy method, recommend ≥1 catalog alternative with the same analysis intent and lower cost class
- [x] Clearly state the trade-off of the lighter option
- [x] User can accept the alternative in one action
- [x] Typecheck passes
- [ ] Verify in browser using dev-browser skill (web) — CLI equivalent prints the recommendation

**As built:** `CostAssessment.alternatives` carries `{method_id, trade_off}`; surfaced in both CLI table and web `recommendations[].alternatives`.

### US-008: Run the selected method and produce a result object ✅
**Description:** As a user, I want to run my chosen (approved) method and get a structured, inspectable result.

**Acceptance Criteria:**
- [x] Execute the method against the canonical input from US-002
- [x] Return a structured result (statistics, p-values/effect sizes, coordinates, cluster labels, etc.) plus the exact parameters used
- [x] Record provenance: input dataset hash, method id + version, parameters, timestamp
- [x] Surface failures (e.g. singular matrix, assumption violation) as actionable messages, not stack traces
- [x] Typecheck passes

**As built beyond spec:** `run()` also attaches `_confidence_band` and `_validation_checks` from the deterministic validation harness — see US-017. Missing input data raises `MissingRequirementError` naming the BGCFlow tool required.

### US-009: Method swapping without re-ingesting ◐
**Description:** As a user, I want to switch to a different valid method and re-run instantly on the same loaded data.

**Acceptance Criteria:**
- [x] Swapping method re-runs cost check → run → viz → interpretation without re-reading disk
- [ ] **Previous result is retained for side-by-side comparison (at least the last 2 runs)** — *not implemented*
- [x] Swap completes with a single action (`--method` flag in CLI; method card in web)
- [x] Typecheck passes
- [ ] Verify in browser using dev-browser skill

**Gap:** the web session stores only `_session["last_result"]`, overwritten on each `/api/run`. There is no run history and no comparison endpoint. This blocks US-013.

### US-010: Visualization recommendation + render ◐
**Description:** As a user, I want the visualization that best fits my data + method, rendered cleanly and defensibly.

**Acceptance Criteria:**
- [x] Map (result type × analysis intent) → recommended chart type
- [x] Render publication-quality figures (consistent theme, readable fonts, colorblind-safe palette, axis labels)
- [ ] **Offer 1–2 alternative valid chart types the user can switch to** — *`recommend_chart()` exists but alternatives are not exposed in either surface*
- [x] Export figure as SVG + PNG
- [x] Typecheck passes
- [ ] Verify in browser using dev-browser skill

**As built:** `viz.render(result, metadata) -> (svg_bytes, png_bytes)`, rendered engine-side so CLI and web emit identical figures.

### US-011: Plain-language, cited interpretation ✅
**Description:** As a wet-lab user, I want a clear explanation of what the result means, with caveats and citations, so I can act on it and write it up.

**Acceptance Criteria:**
- [x] Generate an interpretation stating: what was tested, the result in plain language, effect size/significance in context, and explicit caveats
- [x] Cite the method (from catalog) and reference the exact source tables used
- [x] Interpretation is grounded strictly in the computed result object — no claims beyond the numbers
- [x] Include a short "what this does NOT tell you" section
- [x] Typecheck passes
- [ ] Verify in browser using dev-browser skill

**As built:** three stages — `facts.extract_facts()` (deterministic) → `templates.render_template()` (deterministic) → `llm.rephrase()` (optional, gated). The LLM receives only the facts object and template text, never raw data. Four hard goals gate acceptance (`fidelity`, `structure`, `no_preamble`, `substance`); one retry with a stricter prompt; failure falls back to the template verbatim. Soft goals are LLM-judged and advisory only.

### US-012: Shared engine behind CLI + web, with reproducible export ◐
**Description:** As a bioinformatician, I want the exact analysis reproducible from the command line and exportable as config.

**Acceptance Criteria:**
- [x] Core engine is a library both surfaces import; no analysis logic in the UI
- [ ] **CLI can run the full flow non-interactively from a config file** — *not implemented; `run` takes `--method` and `--params` JSON, not a config file*
- [ ] **A web-app session can export its choices as that same config file** — *not implemented*
- [x] Provenance record (US-008) is written to disk alongside outputs
- [x] Typecheck passes

**As built:** `core/api.py` exposes exactly three functions — `open_project`, `recommend`, `run`. **Deviation from the design doc:** `visualize()` and `interpret()` were specified as engine API functions but live in `bgclens.viz` and `bgclens.interpret`, imported directly by both surfaces. Parity holds (both call the same modules) and is asserted by the 11-test parity suite, but the engine API surface is narrower than designed.

`RunRecord` round-trips as YAML and is the de-facto config format; what's missing is a CLI flag to *load* one.

### US-013 (Phase 2): Multi-run comparison dashboard ○
**Description:** As a user, I want to compare several methods/visualizations side by side to choose the most robust story.

**Acceptance Criteria:**
- [ ] Grid view of ≥3 runs (method, key stat, figure thumbnail, cost)
- [ ] Flag where methods disagree
- [ ] Verify in browser using dev-browser skill

**Blocked on US-009's run-history gap.**

### US-014 (Phase 2): Report bundle export ◐
**Description:** As a user, I want to export a shareable bundle (figures + interpretation + provenance + citations) matching BGCFlow's report style so it drops into existing reports.

**Acceptance Criteria:**
- [x] Export HTML/Markdown bundle with embedded figures, interpretation, and full provenance
- [ ] **Optionally emit as MkDocs pages compatible with `bgcflow serve`** — *not implemented*
- [ ] Verify in browser using dev-browser skill

**As built (deviation):** shipped as **Quarto**, not MkDocs. `bgclens report <run_id>` → `report.render()` writes `{method_id}_{method_hash}.qmd` and shells out to `quarto render` for HTML when the binary is on PATH; degrades to `.qmd`-only otherwise and never raises. The `.qmd` embeds a firewall badge (`precedent` if the run carried literature, else `deterministic`), the figure (inline SVG or base64 PNG), the interpretation, and a JSON provenance block.

### US-015 (Phase 3): User-extensible method plugins ○
**Description:** As an advanced user, I want to register my own method into the catalog so my custom stat is available with the same cost/viz/interpret machinery.

**Acceptance Criteria:**
- [ ] Documented plugin interface (input type, run fn, output type, citation, cost model)
- [ ] A registered plugin appears in the intent-filtered menu
- [ ] Typecheck passes

**Note:** the mechanism already works — the registry glob-loads `catalog/entries/*.yaml` and resolves `impl`/`cost_model` dotted paths. What's missing is a documented, supported public interface and out-of-tree entry discovery.

---

## Stories built beyond the original spec

These were implemented but never specified. They are recorded here so the PRD matches the codebase.

### US-016: Scientific-question (SQ) intents ✅
**Description:** As a researcher, I want to pick my analysis by the *scientific question* I'm asking, not by the statistical family it belongs to.

**As built:** seven SQ intents sit alongside the original six, each with a human-readable label in `SQ_LABELS`:

| Intent | Label | Requires |
|---|---|---|
| `sq1_inventory` | Inventory — what / how many BGCs? | `bgc_counts` |
| `sq2_novelty` | Novelty — known vs new? | `gcf_presence_absence` |
| `sq3_prioritization` | Prioritization — which to chase in the lab? | `gcf_presence_absence` |
| `sq4_distribution` | Distribution — how spread across strains/taxa? | `bgc_counts` |
| `sq5_diversity` | Diversity / sampling — how diverse, is it saturated? | `gcf_presence_absence` |
| `sq6_genomic_context` | Genomic context — core vs accessory, resistance, HGT | `gcf_network` |
| `sq7_association` | Association — do BGCs track phenotype/metadata? | `gcf_presence_absence` |

Each catalog YAML carries an `sq:` tag list mapping methods onto these questions. **Gap:** not surfaced by the web `/api/intents` endpoint.

### US-017: Deterministic validation harness with confidence bands ✅
**Description:** As a user, I want a machine-checkable signal that a method's output is internally coherent, independent of whether its assumptions were met.

**As built:** `validation/` runs a per-method registry of deterministic checks against the result dict and returns a `ValidationResult` with a `confidence_band` of `green` (≥80% checks pass), `amber` (≥50%, and the default when no validators exist), or `red`. Checks never raise — an exception becomes a failed check.

Examples: ordination asserts explained variance sums to 1.0 ± 0.01 and that coordinate width matches the component count; enrichment asserts p-values lie in [0,1]; PERMANOVA asserts both R² and p-value are present and in range.

`api.run()` attaches `_confidence_band` and `_validation_checks` to every result. This is distinct from `check_assumptions` — assumptions warn about *validity*, validation checks assert *internal coherence*.

### US-018: Manufacturability objective ✅
**Description:** As a natural-products researcher, I want method recommendations reordered toward what I can realistically express and manufacture.

**As built:** `AnalysisRequest.objective = "manufacturability"` triggers `manufacturability/`:

- `compute_features(project) -> TierAFeatures` — derives `n_bgcs`, per-class counts, mean GC content, and a **tractability score**: a count-weighted average of per-BGC-class heterologous-expression constants (RiPP 0.9 … PKS-I 0.4; "PKS-I hardest, RiPPs easiest"). Never raises; failures land in `notes`.
- `compute_profile(features) -> ManufacturabilityProfile` — condenses to `{tractability_score, n_bgcs, top_class, notes}`.
- `reorder_for_manufacturability(recs, profile)` — score ≥0.7 boosts `{fisher_enrichment, diversity}` (exploit); <0.5 boosts `{pcoa, pca, clustering}` (explore diversity); 0.5–0.7 leaves order unchanged.

**Caveat:** the tractability constants are a literature-informed heuristic, not a fitted model. `TierAFeatures.mean_cluster_size_kb` is declared but never populated.

### US-019: Quarto report rendering ✅
See US-014 — shipped as the Quarto path rather than the specified MkDocs path.

## Functional Requirements

Status column reflects the implementation as of 2026-07-10.

| | Requirement | Status |
|---|---|---|
| **FR-1** | Accept a path to a completed BGCFlow processed project (directory and/or DuckDB) and produce a manifest of available datasets. | ✅ |
| **FR-2** | Normalize BGCFlow outputs into a fixed set of canonical data structures joined on `genome_id`. | ✅ |
| **FR-3** | Capture a free-text topic plus a structured analysis intent and filter the method catalog to methods valid for the available data. | ✅ |
| **FR-4** | Maintain a versioned, data-driven catalog of post-processing methods, each with a real implementation, constraints, and a citation. | ✅ |
| **FR-5** | Query a scholarly provider (OpenAlex by default, pluggable) to rank valid methods by literature support and attach real citations; never fabricate sources; degrade gracefully offline. | ✅ |
| **FR-6** | Before running, estimate compute cost from input size and complexity, detect available resources, and classify Safe / Heavy / Likely-to-fail. | ✅ |
| **FR-7** | When a method is Heavy or Likely-to-fail, recommend a lower-cost same-intent alternative and state the trade-off. | ✅ |
| **FR-8** | Execute an approved method and return a structured result with full provenance (input hash, method id, params, timestamp). | ✅ |
| **FR-9** | Allow swapping to another valid method, re-running cost-check → execution → viz → interpretation on already-loaded data, **retaining prior results for comparison**. | ◐ retention missing |
| **FR-10** | Recommend and render a publication-quality, colorblind-safe visualization, **with ≥1 valid alternative** and SVG+PNG export. | ◐ alternatives not exposed |
| **FR-11** | Produce a plain-language interpretation grounded strictly in the computed result, with caveats, a "what this does not tell you" section, and citations. | ✅ |
| **FR-12** | Expose the above through both a web GUI and a CLI backed by one shared engine, **with interchangeable config export/import**. | ◐ import not built |

**Requirements added during implementation:**

- **FR-13:** Every method result must carry a deterministic `confidence_band` (`green`/`amber`/`red`) derived from per-method internal-coherence checks that never raise. *(US-017)*
- **FR-14:** The intent space must support scientific-question framing (SQ1–SQ7) alongside statistical-family framing, with each catalog entry declaring which questions it answers. *(US-016)*
- **FR-15:** An optional `objective` on the analysis request may reorder recommendations; the `manufacturability` objective reorders by a BGC-class-derived heterologous-expression tractability score. *(US-018)*
- **FR-16:** A completed run must be renderable to a standalone report (Quarto `.qmd`, plus HTML when `quarto` is on PATH) embedding figure, interpretation, and provenance. Rendering must never raise. *(US-019)*

## Design Considerations

- **Two-persona UI.** Web app defaults to a guided, wizard-like flow (ingest → ask → recommend → run → view → interpret) with sensible defaults for Bianca. Dev's CLI mirrors the same stages as subcommands/flags.
- **Progressive disclosure.** Show the recommended method and figure first; keep "alternatives", "assumptions", and "cost detail" one click away.
- **Trust signals everywhere.** Citations, "approximate" labels on estimates, and explicit caveats are first-class UI, not footnotes — this is a science tool.
- **Reuse BGCFlow's visual language** where sensible so exported figures/reports feel native to an existing BGCFlow workflow.
- Colorblind-safe palettes and readable typography are requirements, not polish.

## Technical Considerations

- **Strictly downstream of BGCFlow** — read-only against its output; never invoke or mutate BGCFlow itself.
- **Read from DuckDB when available** (BGCFlow's OLAP DB) for speed, CSV/TSV fallback otherwise.
- **Scholarly providers** — OpenAlex is the default (free, open, good coverage, no key required). The literature layer sits behind a `LiteratureProvider` protocol; **Europe PMC and MIBiG also ship**, selectable via `get_provider(name)` or the `BGCLENS_LITERATURE_PROVIDER` env var. Queries cached 7 days.
- **Method implementations** should lean on established, citable libraries (scipy, scikit-bio, scikit-learn, statsmodels, networkx) so results are trustworthy and the citation maps to real software.
- **Resource detection** must handle both single workstations and HPC/SLURM contexts (BGCFlow itself targets Linux + conda/mamba, so assume that baseline).
- **Provenance is mandatory** for every run — this is the backbone of reproducibility and the CLI/web parity requirement.
- **Guard against LLM overreach** in the interpretation and literature layers: the LLM ranks/explains/summarizes over *retrieved* data and *computed* results only.

## Success Metrics

| Metric | Status |
|---|---|
| A wet-lab user goes from a finished BGCFlow project to an interpreted, cited figure in under 15 minutes with no code. | Achievable via `bgclens web`; not formally timed with a user |
| ≥90% of offered methods carry a valid literature citation, or are explicitly labeled "no strong literature match". | Enforced structurally — the ranker cannot emit an unsourced citation |
| Zero method runs that silently crash the machine — heavy/failing methods caught before execution in ≥95% of cases. | Cost advisor gates on a 70% RAM headroom; not measured against a failure corpus |
| A method swap re-renders result + figure + interpretation without re-reading disk. | ✅ (session holds the loaded `Project`) |
| A CLI run and a web run from the same config produce byte-identical provenance except timestamp. | ✅ asserted by the 11-test parity suite |

**Test suite:** 176 passing, 15 skipped. The 15 skips are LLM-endpoint and network-gated tests.

| Suite | Tests |
|---|---|
| Unit (14 modules) | includes `test_validation`, `test_manufacturability`, `test_quarto_report`, `test_llm_harness` |
| Integration | walking skeleton, CLI↔web parity, web API, LLM goals, BGCFlow end-to-end (env-gated) |

## Resolved Decisions

Every Open Question from the original PRD has been answered by the implementation.

| Question | Decision as built |
|---|---|
| **Interpretation engine:** template vs LLM? | **Template-first, deterministic.** Facts extraction and templating always run and are the source of truth. LLM phrasing is optional (`BGCLENS_LLM_ENABLED`), receives only the facts object and template text, and must pass four hard goals — `fidelity`, `structure`, `no_preamble`, `substance`. One stricter retry, then verbatim template fallback. The LLM cannot introduce a number. |
| **Literature hallucination guardrail:** what validates that a citation supports "method X used for topic Y"? | **Method+topic co-occurrence in title/abstract.** A citation qualifies only if both the method term and a topic term appear. Below-threshold methods are labelled "valid, no strong literature match" — never dropped, never given fabricated citations. Provider unreachable → literature step skipped and labelled. Thresholds: ≥10 strong, ≥3 moderate, ≥1 weak. |
| **Where does compute detection stop?** | **Local `psutil` + read-only `sinfo`.** No job submission. 70% RAM headroom margin. |
| **Statistical safety net for violated assumptions?** | **Two separate mechanisms.** `check_assumptions` per method *warns* about validity (e.g. unbalanced PERMANOVA groups) and carries warnings verbatim into interpretation caveats — it does not block. The `validation/` harness independently asserts *internal coherence* of the output and emits a green/amber/red confidence band. Only the compute advisor gates. |
| **Catalog ownership?** | **In-repo YAML + CI validation.** `registry.validate_catalog()` rejects any entry lacking a resolvable `impl`, a `cost_model`, or a `citation`. **Still open:** no named domain reviewer has been designated. A wrong statistic with a confident interpretation remains this product's worst failure mode. |
| **Multiple-testing correction?** | **On by default (Benjamini–Hochberg FDR)**, exposed as the `correction` param (`bh`/`bonferroni`/`none`) with `alpha`. Both raw and adjusted p-values are stored; interpretation reports the adjusted value. |
| **Name.** | **BGCLens**, no longer provisional. |

## Known Gaps

Carried forward as the actionable backlog.

1. **Run history / multi-run comparison** (US-009, US-013) — the web session overwrites `last_result`; nothing is retained. Blocks the comparison dashboard.
2. **Config-file round-trip** (US-012) — `RunRecord` serialises but no surface loads one back. The reproducibility story is one flag short of complete.
3. **Web `/api/intents` is stale** — hardcodes the original 6 intents; the 7 SQ intents (US-016) are unreachable from the frontend.
4. **`ranker.rank_methods()` mislabels the provider** — always reports `"openalex"` on success regardless of which backend ran.
5. **Alternative chart types** (US-010) — `recommend_chart()` computes them; neither surface exposes the switch.
6. **`TierAFeatures.mean_cluster_size_kb`** is declared but never populated.
7. **No designated catalog reviewer** — the CI gate checks structure, not scientific correctness.
