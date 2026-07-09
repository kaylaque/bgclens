# PRD: BGCLens — Post-Processing & Interpretation Layer for BGCFlow

> Working name: **BGCLens** (provisional — rename freely). A downstream companion to BGCFlow that turns raw pipeline output into interpretable, method-flexible, literature-grounded, publication-ready results.

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

### US-001: Ingest a BGCFlow project and detect what ran
**Description:** As a user, I want BGCLens to read a finished BGCFlow project directory so it knows which analyses are available to post-process.

**Acceptance Criteria:**
- [ ] Accept a path to a BGCFlow `data/processed/<project>` directory (and/or its DuckDB file)
- [ ] Detect which pipelines produced output (antismash, bigscape, bigslice, gecco, checkm, gtdbtk, arts, roary/pangenome, mash/fastani)
- [ ] Return a structured "capabilities manifest" listing available datasets and their shapes (e.g. GCF presence/absence matrix: N genomes × M GCFs)
- [ ] Fail gracefully with a clear message if the path is not a valid BGCFlow project
- [ ] Typecheck/lint passes

### US-002: Load core result tables into a normalized in-memory model
**Description:** As a developer, I need BGCFlow's heterogeneous outputs mapped into a small set of canonical data structures so downstream methods don't care which tool produced them.

**Acceptance Criteria:**
- [ ] Define canonical types: `PresenceAbsenceMatrix`, `FeatureCountTable`, `TaxonomyTable`, `QualityTable`, `NetworkEdgeList`, `MetadataTable`
- [ ] Load BiG-SCAPE GCF presence/absence, BGC-per-genome counts, and MIBiG-known-cluster tables into these types
- [ ] Load genome metadata (taxonomy, quality) and join on `genome_id`
- [ ] Read from DuckDB when present, fall back to CSV/TSV files
- [ ] Unit tests cover at least one real BGCFlow demo dataset (e.g. the public `mq_saccharopolyspora` demo)
- [ ] Typecheck passes

### US-003: Capture the research question / topic
**Description:** As a user, I want to state what I'm actually asking (e.g. "which BGC classes are enriched in one clade vs another?") so BGCLens can recommend relevant methods.

**Acceptance Criteria:**
- [ ] Free-text topic input plus a structured "analysis intent" picker (enrichment / diversity / ordination / clustering / comparison / network structure)
- [ ] Map the intent to the subset of the method catalog that is valid for the available data (from US-001 manifest)
- [ ] If the intent is incompatible with available data, explain why and suggest what BGCFlow pipeline would need to have run
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-004: Curated method catalog (seed)
**Description:** As a developer, I need a validated, versioned catalog of post-processing methods so every offered option is real and correctly implemented.

**Acceptance Criteria:**
- [ ] Catalog entries include: id, name, analysis intent(s), required input type, output type, implementation reference (library + function), assumptions/constraints, and a canonical citation
- [ ] Seed with at least: Fisher's exact / hypergeometric enrichment; PCA and PCoA; NMDS; PERMANOVA; hierarchical clustering; Shannon & Simpson diversity + rarefaction; network community detection (e.g. Louvain/Leiden) for GCF networks
- [ ] Each entry maps to a concrete, tested implementation (scipy/scikit-bio/scikit-learn/networkx or equivalent)
- [ ] Catalog is data (YAML/JSON), not hardcoded, so it can grow without code changes
- [ ] Typecheck passes

### US-005: Literature-grounded method ranking via scholarly MCP
**Description:** As a user, I want BGCLens to tell me which of the valid methods the literature actually uses for my topic, with citations, so my choice is defensible.

**Acceptance Criteria:**
- [ ] Integrate a scholarly MCP (OpenAlex primary; pluggable so Europe PMC / Semantic Scholar can be added)
- [ ] Given the topic + candidate methods, query the MCP for relevant works and surface: which methods appear in the corpus, rough frequency/recency, and 2–5 representative citations per method
- [ ] Rank catalog methods by literature support for this topic; clearly separate "commonly used in this area" from "valid but rarely used here"
- [ ] Every surfaced claim links to a real source; if the MCP returns nothing, say so and fall back to catalog defaults (never fabricate citations)
- [ ] Cache/rate-limit MCP calls; degrade gracefully when offline
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-006: Compute-cost estimation for a candidate method
**Description:** As a user, I want to know whether a method will actually run on my machine before I start it.

**Acceptance Criteria:**
- [ ] Estimate cost from input dimensions × method complexity class (e.g. PERMANOVA permutations scale with N; distance matrices are O(N²) memory)
- [ ] Detect available resources (CPU cores, RAM; detect if on a known scheduler like SLURM)
- [ ] Classify each candidate method as: Safe / Heavy (warn) / Likely-to-fail (gate) for this dataset on this machine
- [ ] Estimates are labeled as approximate, with the driving factor shown (e.g. "dominated by N=2,400 pairwise distances")
- [ ] Typecheck passes

### US-007: Lighter-alternative recommendation
**Description:** As a resource-constrained user, I want BGCLens to suggest a cheaper method that answers the same question when my first choice is too heavy.

**Acceptance Criteria:**
- [ ] For a gated/heavy method, recommend ≥1 catalog alternative with the same analysis intent and lower cost class (e.g. PCoA on a subsample, or approximate community detection)
- [ ] Clearly state the trade-off of the lighter option (what precision/assumption is sacrificed)
- [ ] User can accept the alternative in one action
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill (web) — CLI equivalent prints the recommendation

### US-008: Run the selected method and produce a result object
**Description:** As a user, I want to run my chosen (approved) method and get a structured, inspectable result.

**Acceptance Criteria:**
- [ ] Execute the method against the canonical input from US-002
- [ ] Return a structured result (statistics, p-values/effect sizes, coordinates, cluster labels, etc.) plus the exact parameters used
- [ ] Record provenance: input dataset hash, method id + version, parameters, timestamp
- [ ] Surface failures (e.g. singular matrix, assumption violation) as actionable messages, not stack traces
- [ ] Typecheck passes

### US-009: Method swapping without re-ingesting
**Description:** As a user, I want to switch to a different valid method and re-run instantly on the same loaded data.

**Acceptance Criteria:**
- [ ] Swapping method re-runs US-006 (cost check) → US-008 (run) → viz → interpretation without re-reading disk
- [ ] Previous result is retained for side-by-side comparison (at least the last 2 runs)
- [ ] Swap completes with a single action (dropdown/select in web; `--method` flag or interactive prompt in CLI)
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-010: Visualization recommendation + render
**Description:** As a user, I want the visualization that best fits my data + method, rendered cleanly and defensibly.

**Acceptance Criteria:**
- [ ] Map (result type × analysis intent) → recommended chart type (e.g. ordination → scatter with grouping; enrichment → dot/volcano; diversity → box/violin + rarefaction curve; network → node-link or matrix; presence/absence → clustered heatmap)
- [ ] Render publication-quality figures (consistent theme, readable fonts, colorblind-safe palette, axis labels with units)
- [ ] Offer 1–2 alternative valid chart types the user can switch to
- [ ] Export figure as SVG + PNG (and vector-friendly for publication)
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-011: Plain-language, cited interpretation
**Description:** As a wet-lab user, I want a clear explanation of what the result means, with caveats and citations, so I can act on it and write it up.

**Acceptance Criteria:**
- [ ] Generate an interpretation that states: what was tested, the result in plain language, effect size/significance in context, and explicit caveats (assumptions, sample size, multiple-testing)
- [ ] Cite the method (from catalog) and reference the exact source tables used
- [ ] Interpretation is grounded strictly in the computed result object — no claims beyond the numbers
- [ ] Include a short "what this does NOT tell you" section
- [ ] Typecheck passes
- [ ] Verify in browser using dev-browser skill

### US-012: Shared engine behind CLI + web, with reproducible export
**Description:** As a bioinformatician, I want the exact analysis reproducible from the command line and exportable as config.

**Acceptance Criteria:**
- [ ] Core engine (ingest → catalog → run → viz → interpret) is a library both surfaces import; no logic duplicated in the UI
- [ ] CLI can run the full flow non-interactively from a config file (project path, intent, method, params)
- [ ] A web-app session can export its choices as that same config file (and vice versa: CLI config loads into the web app)
- [ ] Provenance record (US-008) is written to disk alongside outputs
- [ ] Typecheck passes

### US-013 (Phase 2): Multi-run comparison dashboard
**Description:** As a user, I want to compare several methods/visualizations side by side to choose the most robust story.

**Acceptance Criteria:**
- [ ] Grid view of ≥3 runs (method, key stat, figure thumbnail, cost)
- [ ] Flag where methods disagree
- [ ] Verify in browser using dev-browser skill

### US-014 (Phase 2): Report bundle export
**Description:** As a user, I want to export a shareable bundle (figures + interpretation + provenance + citations) matching BGCFlow's MkDocs style so it drops into existing reports.

**Acceptance Criteria:**
- [ ] Export HTML/Markdown bundle with embedded figures, interpretation, method + data citations, and full provenance
- [ ] Optionally emit as MkDocs pages compatible with `bgcflow serve`
- [ ] Verify in browser using dev-browser skill

### US-015 (Phase 3): User-extensible method plugins
**Description:** As an advanced user, I want to register my own method into the catalog so my custom stat is available with the same cost/viz/interpret machinery.

**Acceptance Criteria:**
- [ ] Documented plugin interface (input type, run fn, output type, citation, cost model)
- [ ] A registered plugin appears in the intent-filtered menu
- [ ] Typecheck passes

## Functional Requirements

- **FR-1:** The system must accept a path to a completed BGCFlow processed project (directory and/or DuckDB) and produce a manifest of available datasets.
- **FR-2:** The system must normalize BGCFlow outputs into a fixed set of canonical data structures joined on `genome_id`.
- **FR-3:** The system must capture a free-text topic plus a structured analysis intent and filter the method catalog to methods valid for the available data.
- **FR-4:** The system must maintain a versioned, data-driven catalog of post-processing methods, each with a real implementation, constraints, and a citation.
- **FR-5:** The system must query a scholarly MCP (OpenAlex by default, pluggable) to rank valid methods by literature support for the topic and attach real citations; it must never fabricate sources and must degrade gracefully offline.
- **FR-6:** Before running, the system must estimate a method's compute cost from input size and complexity, detect available resources, and classify the method as Safe / Heavy / Likely-to-fail.
- **FR-7:** When a method is Heavy or Likely-to-fail, the system must recommend a lower-cost alternative with the same analysis intent and state the trade-off.
- **FR-8:** The system must execute an approved method and return a structured result with full provenance (input hash, method id/version, params, timestamp).
- **FR-9:** The system must allow swapping to another valid method that re-runs cost-check → execution → visualization → interpretation on already-loaded data in a single action, retaining prior results for comparison.
- **FR-10:** The system must recommend and render a scientifically-appropriate, publication-quality, colorblind-safe visualization for the result, with ≥1 valid alternative and SVG+PNG export.
- **FR-11:** The system must produce a plain-language interpretation grounded strictly in the computed result, including caveats, a "what this does not tell you" section, and method + data citations.
- **FR-12:** The system must expose all of the above through both a web GUI and a CLI backed by one shared engine, with interchangeable config export/import for reproducibility.

## Design Considerations

- **Two-persona UI.** Web app defaults to a guided, wizard-like flow (ingest → ask → recommend → run → view → interpret) with sensible defaults for Bianca. Dev's CLI mirrors the same stages as subcommands/flags.
- **Progressive disclosure.** Show the recommended method and figure first; keep "alternatives", "assumptions", and "cost detail" one click away.
- **Trust signals everywhere.** Citations, "approximate" labels on estimates, and explicit caveats are first-class UI, not footnotes — this is a science tool.
- **Reuse BGCFlow's visual language** where sensible so exported figures/reports feel native to an existing BGCFlow workflow.
- Colorblind-safe palettes and readable typography are requirements, not polish.

## Technical Considerations

- **Strictly downstream of BGCFlow** — read-only against its output; never invoke or mutate BGCFlow itself.
- **Read from DuckDB when available** (BGCFlow's OLAP DB) for speed, CSV/TSV fallback otherwise.
- **Scholarly MCP** — OpenAlex is the primary target (free, open, good coverage, no key required for basic use). Design the literature layer behind an interface so Europe PMC / Semantic Scholar can be swapped in. Respect rate limits; cache aggressively.
- **Method implementations** should lean on established, citable libraries (scipy, scikit-bio, scikit-learn, statsmodels, networkx) so results are trustworthy and the citation maps to real software.
- **Resource detection** must handle both single workstations and HPC/SLURM contexts (BGCFlow itself targets Linux + conda/mamba, so assume that baseline).
- **Provenance is mandatory** for every run — this is the backbone of reproducibility and the CLI/web parity requirement.
- **Guard against LLM overreach** in the interpretation and literature layers: the LLM ranks/explains/summarizes over *retrieved* data and *computed* results only.

## Success Metrics

- A wet-lab user can go from a finished BGCFlow project to an interpreted, cited figure in under 15 minutes with no code.
- ≥90% of offered methods for a given topic carry at least one valid literature citation (or are explicitly labeled "no strong literature match").
- Zero method runs that silently crash the machine — heavy/failing methods are caught by the cost check before execution in ≥95% of cases on the demo datasets.
- A method swap re-renders result + figure + interpretation without re-reading disk.
- A CLI run and a web-app run from the same exported config produce identical result objects (byte-identical provenance except timestamp).

## Open Questions

- **Interpretation engine:** template-based (deterministic, fully controllable) vs LLM-generated (fluent, but needs strict grounding)? MVP could start template-first with LLM phrasing on top. Decision needed.
- **Hallucination guardrails for the literature layer:** what's the exact validation that a returned citation genuinely supports "method X is used for topic Y" vs merely co-occurring? Need a concrete rule.
- **Where does compute detection stop?** SLURM job submission vs just reading `sinfo`/local `psutil`? MVP likely local + read-only cluster info.
- **Statistical safety net:** should BGCLens actively warn when a user picks a method whose *assumptions* are violated by their data (e.g. PERMANOVA with unbalanced groups), and how strongly?
- **Catalog ownership:** who curates and reviews new catalog entries for scientific correctness? A review process is implied by FR-4.
- **Multiple-testing correction:** applied automatically, offered as an option, or both? Affects enrichment interpretation directly.
- **Name.** "BGCLens" is provisional.
