---
marp: true
theme: default
paginate: true
header: ''
footer: 'BGCLens · Supervisor Presentation · 2026'
math: katex
---

<!-- _class: lead -->
<!-- _paginate: false -->

# BGCLens

### Post-processing & interpretation layer for BGCFlow

**Turning BGC tables into defensible, reproducible analysis — one command**

---

## BGCFlow stops at the table; interpretation is still manual and fragile

BGCFlow delivers four CSVs — BGC counts, GCF membership, quality, taxonomy.

**What happens next is unsupported:**

- Analyst picks a method by habit, runs it in a one-off notebook
- Parameters undocumented; colleague can't reproduce it
- Interpretation written by eye, citations from memory
- Figure path breaks when the project directory moves

> The bottleneck is not computation. It is the gap between a finished BGCFlow run and a figure you can put in a paper.

<!-- SPEAKER NOTES
Open with the pain. Every lab running BGCFlow has felt this — the pipeline finishes, you're staring at 4 CSVs, and now you're manually loading them into a notebook you half-remember. BGCLens closes that gap in a single CLI call.
-->

---

## BGCLens: one shared engine, two thin surfaces

**One sentence:** BGCLens ingests a finished BGCFlow project, recommends statistically-appropriate methods for your research question (literature-grounded), runs them, renders figures, and writes an interpretation — with optional LLM-enhanced prose.

**The core insight — CLI and web are skins, not separate tools:**

```
bgclens open /path/to/bgcflow/data/processed/my_project
bgclens recommend /path/to/project --intent ordination --topic "BGC diversity"
bgclens run /path/to/project --method pcoa --output ./results/
```

BGCLens is **read-only** — it never modifies BGCFlow output.

<!-- SPEAKER NOTES
The key design decision: one engine API, two thin entry points. CLI and web both import it directly. Run the same RunSpec through either surface and you get byte-identical provenance. That's the property we come back to throughout.
-->

---

## Architecture: 8 engine modules, two thin surfaces

```
┌──────────────── Engine (bgclens/) ────────────────────┐
│  adapters/   detect pipelines, load CSV / DuckDB       │
│  model/      canonical Pydantic types                  │
│  catalog/    YAML method registry + implementations    │
│  compute/    resource probe + cost advisor             │
│  literature/ OpenAlex client + co-occurrence ranker    │
│  viz/        matplotlib → SVG + PNG bytes              │
│  interpret/  facts → template → optional LLM (guarded) │
│  core/       API, session, provenance, config          │
└────────────────────────────────────────────────────────┘
        ↑                        ↑
 bgclens_cli/             bgclens_web/
 Typer (4 cmds)           FastAPI (5 endpoints)
                          + self-contained HTML wizard
```

Engine imported directly — no inter-process calls, no serialization overhead.

<!-- SPEAKER NOTES
Architecture is deliberately boring: one Python package, two thin wrappers. All complexity budget went into the engine, not the plumbing.
-->

---

## Ingest: detect pipelines without a config file

```bash
bgclens open /path/to/bgcflow/data/processed/mq_saccharopolyspora

# ✔ Project loaded: mq_saccharopolyspora
# Pipelines: antismash, bigscape, bigslice, checkm, gtdbtk, mash
# GCF matrix: 312 GCFs × 26 genomes
# BGC counts: 26 genomes × 6 BGC classes
```

**Detection strategy (adapters/):**

- Scan directory for known output filenames from each BGCFlow module
- No config file required — presence of files is the signal
- **DuckDB preferred** when present; **CSV/TSV fallback** otherwise

<!-- SPEAKER NOTES
The adapter layer does one thing: given a directory, tell me which pipelines ran and produce strongly-typed dataframes. Downstream code never touches raw CSVs. DuckDB preferred because BiG-SCAPE network files can be millions of edges.
-->

---

## Canonical model: 6 Pydantic types, one join key (`genome_id`)

| Type | Class | Source |
|------|-------|--------|
| BGC counts | `FeatureCountTable` | antiSMASH summary |
| GCF presence/absence | `PresenceAbsenceMatrix` | BiG-SCAPE clusters |
| Genome quality | `QualityTable` | CheckM |
| Taxonomy | `TaxonomyTable` | GTDB-Tk |
| GCF network edges | `NetworkEdgeList` | BiG-SCAPE network |
| Metadata join hub | `MetadataTable` | merged on `genome_id` |

All cross-dataset joins happen on `genome_id`. Methods only ever receive canonical types — never raw CSVs or DataFrames.

<!-- SPEAKER NOTES
The canonical model is the spine. Adapters map heterogeneous BGCFlow output into these six types. Every downstream method only sees typed objects — if a new BGCFlow pipeline produces a new file format, you write one adapter; nothing else changes.
-->

---

## Method catalog: adding a method is one YAML file + one function

```yaml
# bgclens/catalog/entries/permanova.yaml
id: permanova
name: PERMANOVA (Permutational ANOVA of distances)
intents: [comparison]
requires: {presence_absence: presence_absence_matrix}
params:
  permutations: {default: 999}
  correction:   {default: bh}
assumptions: [two_groups_in_metadata, min_group_n_3]
cost_model: bgclens.catalog.methods.permanova:cost
impl:       bgclens.catalog.methods.permanova:run
citation:
  doi: "10.1111/j.1442-9993.2001.01070.pp.x"
  note: "Anderson 2001 PERMANOVA"
```

The registry glob-loads all `catalog/entries/*.yaml` at startup. **No engine, CLI, or web changes needed to add a method.**

<!-- SPEAKER NOTES
This is the extensibility story. Adding Jaccard-based NJ clustering next month means one new YAML and one new Python module with run() and cost(). Nothing else changes. The citation field feeds the literature ranker directly.
-->

---

## Literature-grounded recommendation: co-occurrence, not opinion

**Problem:** which method suits "BGC diversity across clades" is answered by what the community publishes — not by documentation.

**Solution (literature/):**
1. Query OpenAlex for papers matching the user's topic
2. Extract method co-occurrences from abstracts
3. Rank catalog methods by frequency; return with real DOIs

**The hard constraint:** if OpenAlex returns 0 results → uniform priors, labelled explicitly. No synthetic citations, ever.

<!-- SPEAKER NOTES
Not a RAG pipeline — it's a co-occurrence ranker over real retrieved metadata. If you ask about BGC diversity in marine sediments, you get methods that appear in marine BGC papers. Thin corpus surfaces as "No literature signal — using method defaults". Citations are URLs to retrieved papers, never generated text. The no-fabrication constraint is architectural, not a prompt instruction.
-->

---

## Compute advisor: Safe / Heavy / Likely-to-fail

```python
# compute/advisor.py
_HEADROOM = 0.70   # use at most 70 % of available RAM

def assess(method_id, inputs, params) -> CostAssessment:
    estimate  = cost_fn(inputs, params)     # method's own cost model
    budget_mb = ram_available_mb * _HEADROOM
    cls = "Safe"
    if estimate.mb > budget_mb:        cls = "Heavy"
    if estimate.mb > ram_total_mb*.9:  cls = "Likely-to-fail"
    return CostAssessment(cost_class=cls, alternatives=[...])
```

Assumption checks run **before** compute: `min_genomes_5`, `two_groups_in_metadata`, `group_balance_warning`.

<!-- SPEAKER NOTES
The advisor prevents the common failure: researcher queues PERMANOVA with 999 permutations on a 1,000-genome dataset, laptop OOMs 45 minutes in. The advisor intercepts at recommend time and suggests a lighter alternative with the trade-off noted.

The three assumption checks: min_genomes_5 (PCoA is meaningless on 3 genomes), two_groups_in_metadata (PERMANOVA needs a grouping column), group_balance_warning (unbalanced groups inflate false-positive rate). Warnings are shown; analysis still runs unless inputs are structurally invalid.
-->

---

## Interpretation pipeline: facts first, then prose

```
result dict
    │
    ├─ InterpretationFacts   ← typed: key_numbers, group_labels, significant
    │        │
    │        ├─ Template renderer    ← deterministic, always runs
    │        │   "PERMANOVA R²=0.43 (p=0.001, 999 perms, Bray-Curtis)"
    │        │
    │        └─ LLM phrasing         ← optional (BGCLENS_LLM_ENABLED=true)
    │                 │
    │                 └─ Guard layer  ← strip sentences with foreign numbers/DOIs
    │
    └─ Figure (SVG + PNG)    ← rendered engine-side, identical CLI/web
```

Guard drops any sentence that introduces a number, DOI, or accession not in `facts.key_numbers` — LLM output cannot add new claims.

<!-- SPEAKER NOTES
The guard layer is the second architectural no-fabrication guarantee. Even if the LLM hallucinates "a significant p-value of 0.003", the guard strips that sentence because 0.003 wasn't in the facts object. What remains is stylistically polished prose that cannot introduce new claims.
-->

---

## Provenance: every run is reproducible and portable

```yaml
# bgclens_run_a3f91b2c.yaml  (written on every run)
bgclens_run:
  project_path: /data/processed/mq_saccharopolyspora
  inputs_hash:  sha256:a3f91b2c...     # stable: path + file mtimes
  run_spec:
    method: permanova
    params: {permutations: 999, correction: bh}
    intent: comparison
  llm:
    model: gpt-4o-mini
    api_key_present: true              # key is NEVER written to file
  result_summary:
    r_squared: 0.43
    p_value:   0.001
```

**CLI ↔ web parity:** web wizard serialises an identical RunRecord. Import that YAML into the CLI → same run, same hash, same figures.

<!-- SPEAKER NOTES
The RunRecord is the reproducibility unit. A collaborator takes your bgclens_run_*.yaml, points it at the same BGCFlow directory, and gets identical figures. The inputs_hash catches if the underlying BGCFlow data changed. API key explicitly excluded — safe to commit to the repo.
-->

---

## Demo: install → load → recommend → run

```bash
# Install
pipx install "bgclens[all]"

# Load project
bgclens open /data/processed/mq_saccharopolyspora
# ✔ GCF matrix: 312 GCFs × 26 genomes

# Get literature-grounded recommendation
bgclens recommend /data/processed/mq_saccharopolyspora \
    --intent ordination --topic "BGC diversity across clades"
# ✔ Recommended: pcoa  (literature rank 1, cost: Safe)
# ✔ Alternative: pca   (cost: Safe, trade-off: ignores distances)

# Run and write outputs
bgclens run /data/processed/mq_saccharopolyspora \
    --method pcoa --output ./results/
# ✔ Figure:     results/pcoa_mq_saccharopolyspora.svg
# ✔ Provenance: results/bgclens_run_a3f91b2c.yaml
```

<!-- SPEAKER NOTES
Walk through each command. Step 3 hits OpenAlex in real time — recommendation changes if the topic changes. Step 4 writes provenance before the user reads the figure. Web UI: `bgclens web` opens the same 4-step wizard at localhost:8765.
-->

---

## Test suite: 82 tests, four layers

| Suite | Tests | What it covers |
|-------|------:|----------------|
| Unit (8 modules) | 54 | adapters, catalog, compute, interpret, literature, viz |
| Walking skeleton | 11 | ingest → recommend → run → figure → provenance |
| Provenance parity (CLI ↔ web) | 11 | same RunSpec → identical hash on both surfaces |
| Web API | 6 | FastAPI endpoint contracts |
| **Total** | **82** | |

```bash
uv run pytest tests/ -q    # 82 passed in 16s
```

The **parity suite** is the architectural invariant test: any divergence between CLI and web paths fails it immediately.

<!-- SPEAKER NOTES
The parity suite is the most unusual category. It instantiates the engine twice — once through CLI, once through web API — with the same RunSpec and asserts the provenance hash is identical. That test would catch any logic added to one surface that wasn't added to the other.
-->

---

## Roadmap

**Short-term**
- MIBiG novelty scoring — flag GCFs with no close BiG-SCAPE hit
- CAZy / dbCAN annotation overlay on ordination plots
- `bgclens batch` — all recommended methods, one combined report

**Medium-term**
- MGnify integration — environmental metagenome BGC context
- Comparative mode — two projects, PERMANOVA on merged matrix

Every item lands as a **catalog entry or adapter — not an engine change**.

<!-- SPEAKER NOTES
The roadmap is intentionally modular. MIBiG novelty scoring is a new YAML entry plus a Python function that calls the MIBiG API. Nothing in the engine, CLI, or web changes. That's the payoff of the catalog design decision.

The three extension points already open, all requiring zero engine changes: new method = 1 YAML + 1 Python function; new data source = implement AbstractLoader and register it in adapters; new LLM endpoint = set BGCLENS_LLM_BASE_URL to any OpenAI-compatible endpoint (OpenAI, DeepSeek, Groq, Ollama, LiteLLM, vLLM).
-->

---

<!-- _class: lead -->
<!-- _paginate: false -->

## Three takeaways

1. **The gap is closed** — one command from BGCFlow tables to figure + interpretation + provenance

2. **Recommendations are literature-grounded** — OpenAlex co-occurrence, real DOIs, never fabricated

3. **Built to extend** — YAML catalog, guard-protected interpretation, portable provenance

---

**Repo:** `github.com/your-org/bgclens`
**Install:** `pipx install "bgclens[all]"`
**Demo:** `bgclens web`

---

<!-- _class: lead -->
<!-- _paginate: false -->

## Open Items

*Figures to add before presenting:*

- `FIGURE_PLACEHOLDER_pcoa_example_plot.png` — PCoA scatter coloured by taxonomy (slide 14)
- `FIGURE_PLACEHOLDER_web_wizard_screenshot.png` — 4-step wizard screenshot
- `FIGURE_PLACEHOLDER_literature_ranking_terminal.png` — `bgclens recommend` output with OpenAlex scores
