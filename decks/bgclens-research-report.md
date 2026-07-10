---
marp: true
theme: default
paginate: true
header: ''
footer: 'BGCLens · Research Report · 2026'
math: katex
---

<!-- _class: lead -->
<!-- _paginate: false -->

# BGCLens

### A post-processing and interpretation layer for BGCFlow

Literature-grounded method selection, guarded LLM interpretation,
and reproducible provenance for BGC genome mining

Research Report · 2026

---

## Background: genome mining produces tables faster than it produces understanding

**Biosynthetic gene clusters (BGCs)** encode secondary metabolites — the source of most clinical antibiotics.

- **antiSMASH** predicts BGCs from genomes
- **BiG-SCAPE** groups them into gene cluster families (GCFs) and builds similarity networks
- **BGCFlow** orchestrates these into a reproducible Snakemake pipeline

The pipeline ends at a set of CSVs. **Interpretation begins there — and is unsupported.**

<!-- SPEAKER NOTES
Set the domain. BGCs are the biosynthetic machinery for secondary metabolites; genome mining is how we find novel ones. BGCFlow, from the NBChub group, is the current best-practice orchestrator. It does its job well. The problem is what happens after it finishes.
-->

---

## The gap: from four CSVs to a defensible figure

A completed BGCFlow run yields BGC counts, GCF membership, quality, and taxonomy tables.

**What the analyst does next, today:**

- Chooses a statistical method by habit or by what a previous paper used
- Runs it in an ad-hoc notebook; parameters go undocumented
- Writes the interpretation by eye; recalls citations from memory
- Cannot reproduce the figure six months later

> The bottleneck is not computation. It is the unsupported gap between pipeline output and publishable claim.

<!-- SPEAKER NOTES
This is the research problem. Not a compute problem — a methodology and reproducibility problem. Three failure modes: arbitrary method choice, undocumented parameters, ungrounded interpretation.
-->

---

## Research question

> Can method selection, statistical execution, figure generation, and written
> interpretation be made **reproducible and literature-grounded** for BGC
> genome-mining output — without the analyst editing code?

Three sub-questions:

1. Can we ground method choice in **what the literature actually uses** for a stated topic?
2. Can an LLM improve interpretation prose **without introducing unsupported claims**?
3. Can a GUI and a CLI produce **provably identical** results?

<!-- SPEAKER NOTES
Frame the whole project as three testable claims. Each maps to an architectural component and each has a corresponding test in the suite. Sub-question 1 → the literature service. Sub-question 2 → the four hard goals. Sub-question 3 → the 11-test parity suite. This is the spine of the report.
-->

---

## Method: five load-bearing principles — and where they held

1. **The engine is the product.** CLI and web are thin skins over one library.
   → *Upheld in substance;* surfaces import `viz`/`interpret` directly, not via `core.api`
2. **Figures render engine-side.** matplotlib → SVG+PNG bytes. → *Upheld*
3. **Science is deterministic; the LLM only touches prose.** → *Upheld, and hardened*
4. **The catalog is data, not code.** Methods are YAML. → *Upheld*
5. **Read-only, strictly downstream.** Never mutates BGCFlow. → *Upheld*
6. **Provenance is replayable.** → **Half-upheld — every run writes a record; nothing reads one back**

<!-- SPEAKER NOTES
Principle 3 is the one that matters most scientifically — it's what makes the tool defensible. Be candid about 1 and 6. Principle 1's violation is cosmetic: no analysis logic leaked into a surface, but the single entry point I designed didn't survive. Principle 6's gap is real and it's on the recommendations slide.
-->

---

## Workflow diagram

<style scoped>
section { font-size: 21px; }
</style>

```
  BGCFlow project (read-only)
          │
          ▼
   ┌─────────────┐  detect pipelines · DuckDB → CSV fallback
   │  1. INGEST  │──────────────────────────►  ProjectManifest + 6 canonical types
   └─────────────┘
          │
          ▼
   ┌─────────────┐  intent validation → catalog filter → literature rank
   │ 2. RECOMMEND│──────────────────────────►  cost class (Safe / Heavy / Fail)
   └─────────────┘                             + optional manufacturability reorder
          │
          ▼
   ┌─────────────┐  assumption checks → execute → validation band (green/amber/red)
   │  3. RUN     │
   └─────────────┘
          │
          ├──────────► 4. VISUALIZE  → SVG + PNG (engine-side, deterministic)
          ├──────────► 5. INTERPRET  → facts → template → guarded LLM
          ├──────────► 6. PROVENANCE → bgclens_run_*.yaml (stable input hash)
          └──────────► 7. REPORT     → Quarto .qmd (+ HTML if quarto on PATH)
```

<!-- SPEAKER NOTES
Stages 4–7 fan out from the same result object — independent consumers, which is why a method swap re-enters at stage 2 without re-reading disk. Stage 3 now also emits a confidence band. Stage 7 is new since the original design.
-->

---

## Canonical data model: the contract everything depends on

| Type | Class | BGCFlow source |
|------|-------|----------------|
| BGC counts | `FeatureCountTable` | antiSMASH summary |
| GCF presence/absence | `PresenceAbsenceMatrix` | BiG-SCAPE clusters |
| Genome quality | `QualityTable` | CheckM |
| Taxonomy | `TaxonomyTable` | GTDB-Tk |
| GCF network edges | `NetworkEdgeList` | BiG-SCAPE network |
| Metadata join hub | `MetadataTable` | merged on `genome_id` |

**Rule:** all cross-dataset joins happen on `genome_id`. If a method needs data not loadable into one of these types, it is not in the catalog.

<!-- SPEAKER NOTES
This closes the method↔data contract and makes it testable. Adapters map heterogeneous BGCFlow output into these six types; methods only ever see canonical types. A new BGCFlow pipeline means one new adapter — nothing downstream changes.
-->

---

## Intent space: expanded from six to thirteen

The original six intents name a **statistical family**. Researchers think in **questions**. Seven scientific-question (SQ) intents were added alongside.

| SQ intent | Question | Requires |
|---|---|---|
| `sq1_inventory` | What / how many BGCs? | `bgc_counts` |
| `sq2_novelty` | Known vs new? | `gcf_presence_absence` |
| `sq3_prioritization` | Which to chase in the lab? | `gcf_presence_absence` |
| `sq4_distribution` | How spread across strains/taxa? | `bgc_counts` |
| `sq5_diversity` | How diverse — is sampling saturated? | `gcf_presence_absence` |
| `sq6_genomic_context` | Core vs accessory, resistance, HGT | `gcf_network` |
| `sq7_association` | Do BGCs track phenotype/metadata? | `gcf_presence_absence` |

**Known gap:** the web `GET /api/intents` still exposes only the original six.

<!-- SPEAKER NOTES
The original six — enrichment, diversity, ordination, clustering, comparison, network_structure — remain. Each catalog YAML now carries an `sq:` tag listing which questions it answers, so one method can serve several. The web endpoint was never refreshed; that's item 5 on the recommendations slide.
-->

---

## Features

**Ingestion** — auto-detects which BGCFlow pipelines ran (no config file); DuckDB preferred, CSV fallback

**Recommendation** — intent validation · literature ranking across 3 providers · compute-cost advisor (Safe / Heavy / Likely-to-fail) with lighter alternatives · optional manufacturability reorder

**Execution & output** — 7 statistical methods · deterministic confidence band per result · publication-quality SVG + PNG · guarded LLM interpretation · YAML provenance · Quarto report

**Surfaces** — Typer CLI (`open`, `recommend`, `run`, `report`, `web`) · FastAPI + offline HTML wizard

<!-- SPEAKER NOTES
Group by pipeline stage so the audience maps each back to the workflow diagram. Emphasise that the LLM is optional — the tool is fully functional and scientifically complete without it; the template prose is the source of truth.
-->

---

## Analyses available

| Method | ID | Intent | Requires |
|--------|-----|--------|----------|
| Fisher enrichment | `fisher_enrichment` | enrichment | BGC counts + taxonomy |
| PCoA | `pcoa` | ordination | GCF presence/absence |
| PCA | `pca` | ordination | BGC counts |
| PERMANOVA | `permanova` | comparison | GCF presence/absence + groups |
| Alpha diversity | `alpha_diversity` | diversity | BGC counts |
| Hierarchical clustering | `hierarchical_clustering` | clustering | GCF presence/absence |
| Louvain community | `louvain_community` | network_structure | GCF network edges |

Each entry also carries an `sq:` tag mapping it onto the scientific questions, plus assumptions, a cost model, and a **canonical citation** — all validated in CI.

<!-- SPEAKER NOTES
Seven methods. NMDS was in the original seed list and was never implemented — PCoA and PCA cover the ordination intent. Every method carries a DOI in its YAML, and that citation is surfaced in the interpretation text the user gets back.
-->

---

## Method catalog: adding an analysis is one YAML file

```yaml
# bgclens/catalog/entries/permanova.yaml
id: permanova
name: PERMANOVA (Permutational ANOVA of distances)
intents: [comparison, sq6_genomic_context, sq7_association]
sq:      [sq6_genomic_context, sq7_association]
requires: {presence_absence: presence_absence_matrix, grouping_col: str}
params:
  permutations: {default: 999}
  correction:   {default: bh}     # Benjamini-Hochberg FDR, ON by default
assumptions: [two_groups_in_metadata, min_group_n_3, group_balance_warning]
cost_model: bgclens.catalog.methods.permanova:cost
impl:       bgclens.catalog.methods.permanova:run
citation: {doi: "10.1111/j.1442-9993.2001.01070.pp.x"}
```

CI rejects any entry lacking a resolvable `impl`, a `cost_model`, or a `citation`.

<!-- SPEAKER NOTES
The registry glob-loads every YAML at startup. Adding a method is one file plus one Python module exposing run/cost/check_assumptions. Multiple-testing correction is ON by default — both raw and adjusted p-values are stored, and interpretation always reports the adjusted one.

Important caveat for the next slide-but-one: CI checks that a citation FIELD EXISTS. It does not check that the statistic is correctly implemented for the claim it makes.
-->

---

## Literature service: three providers, one honesty rule

| Provider | Backend | Role |
|---|---|---|
| `OpenAlexProvider` | OpenAlex REST | default; decodes inverted abstracts |
| `EuropePMCProvider` | Europe PMC REST | alternative corpus |
| `MiBiGProvider` | MIBiG API | reference-cluster citations for novelty/precedent |

**The co-occurrence rule.** A method is "literature-supported for topic T" only if returned works contain **both** the method term and a topic term in title/abstract. Below threshold → *"valid, no strong literature match"* — never dropped, never given a fabricated citation.

Thresholds: ≥10 works `strong` · ≥3 `moderate` · ≥1 `weak` · else `none`. Cached 7 days.

<!-- SPEAKER NOTES
This is not a RAG pipeline — it's a co-occurrence ranker over real retrieved metadata. Selection via get_provider(name) or the BGCLENS_LITERATURE_PROVIDER env var; unknown or unset returns None, which triggers the labelled offline fallback. merge_supports() combines providers with citation dedup.

Known defect, on the limitations slide: ranker.rank_methods() hardcodes provider="openalex" on the success path, so a Europe PMC or MIBiG run records the wrong provider in provenance.
-->

---

## LLM architecture: the model never sees data, never adds a number

<style scoped>
section { font-size: 21px; }
</style>

```
   AnalysisResult (numbers)
          │
          ▼
   ┌────────────────────┐  deterministic extraction
   │ InterpretationFacts│  key_numbers, n, significant, direction, caveats
   └────────────────────┘
          │
          ▼
   ┌────────────────────┐  deterministic templating — always runs
   │   Template prose   │  "PERMANOVA F=2.14, p=0.001, n=26"
   └────────────────────┘
          │
          ▼  (optional — BGCLENS_LLM_ENABLED)
   ┌────────────────────┐  input = facts object + template text ONLY
   │   LLM rephrasing   │  never raw data
   └────────────────────┘
          │
          ▼
   ┌────────────────────┐  4 hard goals, all must pass
   │    Guard + Goals   │  else → template returned verbatim
   └────────────────────┘
```

<!-- SPEAKER NOTES
Stages 1 and 2 are deterministic and always run — they are the source of truth. Stage 3 is optional and constrained. The LLM receives only the facts object and the template text, never the raw matrices. If validation fails, the deterministic template is returned unchanged. The user always gets correct prose.
-->

---

## LLM guardrails: four hard goals gate every candidate

| Goal | Check |
|------|-------|
| `fidelity` | Introduces no number, DOI, PMID, or accession absent from the facts object |
| `structure` | Every `##` section header from the template survives |
| `no_preamble` | Does not open with meta-commentary or a code fence |
| `substance` | Non-empty, ≥60 % of template length (no silent content dropping) |

**Failure handling:** one retry with a stricter prompt → if still failing, return the template **verbatim**.

Soft goals (`meaning_preserved`, `fluency_improved`) are LLM-judged and **advisory only** — they never gate.

<!-- SPEAKER NOTES
Designed for a weak model. The deployed endpoint is small, not frontier, so goals are binary and mechanical — that's what a weak model, and a weak judge, can reliably be held to. The fallback is always safe: worst case the user gets correct-but-stiff prose. There is no path where the LLM degrades scientific accuracy.
-->

---

## Validation harness: is the output internally coherent?

A separate question from "were the assumptions met?". Deterministic, never raises.

```python
evaluate(method_id, result) -> ValidationResult   # {checks, confidence_band}
band(passed, total)  # ≥0.8 → green · ≥0.5 → amber · else red · total==0 → amber
```

Examples: ordination asserts explained variance sums to 1.0 ± 0.01 · enrichment asserts p ∈ [0,1] · PERMANOVA asserts R² and p-value present and in range.

**Three layers, three questions, deliberately separate:**

| Layer | Question | On failure |
|---|---|---|
| Compute advisor | Will this *fit*? | **Gates** |
| `check_assumptions` | Is this *valid* for the data? | **Warns** |
| Validation harness | Is the output *coherent*? | **Bands** green/amber/red |

<!-- SPEAKER NOTES
api.run() attaches _confidence_band and _validation_checks to every result. A check that raises becomes a failed check, never an exception. An unknown method gets zero checks and therefore amber — deliberately not green, so absence of evidence never reads as evidence of correctness.
-->

---

## Manufacturability: an optional prioritisation objective

`AnalysisRequest.objective = "manufacturability"` reorders recommendations by a heterologous-expression **tractability score** — a count-weighted average over BGC class composition.

RiPP 0.9 · Terpene 0.85 · NRP 0.7 · NRPS 0.65 · Hybrid 0.55 · PKS-II 0.45 · **PKS-I 0.4**

**Reorder policy** (a stable partition, not a re-scoring):

- score ≥ 0.7 → boost enrichment + diversity *(exploit: clusters are expressible)*
- score < 0.5 → boost PCoA, PCA, clustering *(explore: characterise before bench time)*
- otherwise → unchanged

> **Caveat, stated plainly:** these nine constants are a literature-informed heuristic, not a fitted model, and are not individually cited. Treat as a prioritisation hint, not evidence.

<!-- SPEAKER NOTES
This is the least scientifically grounded part of the system, and it is the part that reorders what the researcher sees first. I want to flag it rather than bury it. Either we cite each class constant, or we label the feature experimental in the UI. mean_cluster_size_kb is declared in TierAFeatures but never populated.
-->

---

## Provenance: export works, replay does not

```yaml
# bgclens_run_a3f91b2c.yaml — written on every run
bgclens_run:
  project_path: /data/processed/mq_saccharopolyspora
  inputs_hash:  sha256:a3f91b2c...          # path + file mtimes
  request:      {topic: "BGC diversity across clades", intent: comparison}
  run_spec:     {method_id: permanova, params: {permutations: 999}}
  llm:          {enabled: true, used: true}  # API key NEVER written
  result_summary: {f_statistic: 2.14, p_value: 0.001, n_genomes: 26}
```

**Tested invariant:** CLI and web produce provenance identical in every field except `created_at` — asserted by 11 parity tests.

**The gap:** no surface *loads* a `RunRecord`. It documents a run; it cannot yet replay one.

<!-- SPEAKER NOTES
The record serves two of its three intended jobs — document and audit. Transfer-and-replay is unbuilt: `bgclens run` takes --method and --params, not --config. This is the single highest-value gap in the reproducibility story and it's item 2 on the recommendations slide. Roughly a day's work.

`bgclens report <run_id>` turns a saved record into a Quarto .qmd, plus HTML when quarto is on PATH. It embeds a firewall badge — "precedent" if the run carried literature support, else "deterministic".
-->

---

## Validation: 176 tests passing

| Suite | Passed | What it establishes |
|-------|-------:|---------------------|
| Unit (14 modules) | 147 | Each engine layer behaves in isolation |
| Walking skeleton | 12 | ingest → recommend → run → figure → provenance |
| Provenance parity (CLI ↔ web) | 11 | Both surfaces produce identical provenance |
| Web API | 6 | FastAPI endpoint contracts hold |
| **Total** | **176** | *(+15 skipped: LLM- and network-gated)* |

The **parity suite** is the architectural invariant test: any logic added to one surface but not the other fails it immediately.

<!-- SPEAKER NOTES
Sub-question 3 — "can a GUI and CLI produce provably identical results?" — is answered by the parity suite, not by assertion. It drives the engine through both paths with the same RunSpec and diffs the provenance. The 15 skips are LLM-endpoint and BGCFlow-end-to-end tests, gated on env vars so the suite stays green offline and on macOS.
-->

---

## Limitations and known gaps

1. **No scientific reviewer on the catalog.** CI validates that a citation *field exists* — not that the statistic is correctly implemented for the claim it makes. **Top risk, and it is organisational, not technical.**
2. **Manufacturability constants are unfitted** — nine hand-set numbers reorder what the researcher sees first.
3. **Provenance mislabels the provider** — Europe PMC / MIBiG runs record `provider: openalex`. Provenance that lies is worse than provenance that is absent.
4. **Reproducibility round-trip is one flag short** — `RunRecord` exports, never imports.
5. **Cost gating was never validated** against a real out-of-memory corpus.
6. Literature ranking is **co-occurrence, not semantic**. Assumption checks **warn, never block**. No cluster job submission — resource detection is read-only.

<!-- SPEAKER NOTES
Lead with risk 1 and do not soften it. A wrong statistic delivered with a confident, fluent interpretation is the worst failure this tool can produce, and the gate designed to catch it does not exist yet. Everything else on this slide is a day or two of work; that one is a decision.
-->

---

## Next recommendations, ranked by payoff

**Closes the known gaps**

1. **Name a catalog reviewer** — zero code, largest risk reduction
2. `bgclens run --config <RunRecord.yaml>` — closes the replay gap, completes the reproducibility claim
3. Fix `ranker.rank_methods()` to report the provider that actually ran
4. Add run history to the web session — unblocks side-by-side method comparison
5. Refresh `GET /api/intents` from the `Intent` enum so SQ intents reach the frontend

**Extends reach**

- MIBiG **novelty scoring** as a catalog method (the provider already ships; the method does not)
- CAZy / dbCAN annotation overlay on ordination plots · `bgclens batch`

<!-- SPEAKER NOTES
Item 1 is the ask. It costs nothing to implement and it is the only item on this list that no amount of engineering can substitute for.

Items 2–5 are each roughly a day. Item 2 is the one that makes the headline reproducibility claim actually true.

Novelty scoring is what a natural-products supervisor will want first — and because the catalog is YAML-driven and the MIBiG provider exists, it costs one entry plus one function.
-->

---

<!-- _class: lead -->
<!-- _paginate: false -->

## Summary

1. **Method choice is grounded in retrieved literature** — co-occurrence across three providers, real DOIs, never fabricated

2. **The LLM improves prose but cannot alter science** — deterministic facts, four hard goals, verbatim fallback

3. **Reproducibility is structural — and one flag from complete** — provenance is written and proven identical across surfaces; replaying it is the next commit

---

## Open items

*To fill before submission:*

- `FIGURE_PLACEHOLDER_pcoa_ordination_by_taxonomy.png` — PCoA scatter, coloured by GTDB genus
- `FIGURE_PLACEHOLDER_gcf_network_louvain.png` — GCF network with Louvain communities
- `FIGURE_PLACEHOLDER_web_wizard_screenshot.png` — 4-step web wizard, Method step
- `FIGURE_PLACEHOLDER_confidence_band_example.png` — a result card showing green/amber/red banding
- `FIGURE_PLACEHOLDER_quarto_report.png` — rendered `bgclens report` HTML output
- Real dataset statistics for a demo project (currently only `mq_saccharopolyspora`: 312 GCFs × 26 genomes)
