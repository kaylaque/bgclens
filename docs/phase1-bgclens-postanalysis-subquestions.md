# Phase 1 — Post-Analysis Inventory & Sub-Question Map (BGCLens)

**Status:** Draft for review · **Depends on:** BGCFlow outputs · **Next gate:** validate with a lab person

---

## 1. Goal of Phase 1

Map what BGCFlow hands the researcher, inventory the post-analyses researchers actually run on those outputs, and organize them into sub-questions under the project's peak question. Output of this phase is a validated sub-question list that anchors MVP scope.

**Peak question:** *What (novel) secondary metabolites does this collection encode, and which are worth chasing?*

**Core reframe:** BGCFlow's pipelines are finite and deterministic. The real variation in post-processing lives in how researchers **join, filter, and interpret** the resulting tables — mostly by hand. That manual join-and-interpret layer is BGCLens's target, so the inventory is organized by *analytical move on the tables*, not by pipeline.

---

## 2. The substrate (what BGCFlow produces)

Grouped by the object each output describes, since post-analyses cut across objects.

| Object level | BGCFlow outputs |
|---|---|
| Genome | CheckM (completeness/contamination), SeqFu (assembly stats), GTDB-Tk (taxonomy), Mash / FastANI (distance, ANI) |
| Gene / protein | Prokka (gene calls), eggNOG (COG/KEGG), DeepTFactor (regulators) |
| BGC region | antiSMASH (regions, classes, MIBiG similarity), GECCO (CRF detection) |
| GCF / family | BiG-SCAPE (networks, clans), BiG-SLiCE + query-bigslice (BiG-FAM mapping) |
| Pangenome | Roary (core / accessory / unique), eggNOG-roary, deeptfactor-roary |
| Prioritization / search | ARTS (resistance-guided), cblaster (homolog search) |
| Aggregate | DuckDB database + Metabase report over all tables |

---

## 3. Post-analysis variation (tiered by universality)

Tiering feeds the catalog scope decision: Tier 1 is the MVP catalog; Tier 3 is the long tail that the non-executing discovery track handles.

### Tier 1 — Near-universal (in almost every genome-mining paper)
- BGC inventory: counts per genome, class distribution (NRPS/PKS/terpene/RiPP…), BGCs per Mbp, vs genome size
- BiG-SCAPE network summary: GCF/clan counts, **singleton fraction** (novelty proxy)
- Novelty scoring: BiG-SCAPE distance to MIBiG + BiG-FAM hit/no-hit → known vs candidate-novel
- Pangenome partition: core / accessory / unique gene counts
- Phylogenetic tree + annotation: GTDB/autoMLST tree with BGC/GCF/metadata rings (iTOL)

### Tier 2 — Common but question-dependent
- GCF presence/absence across phylogeny → lineage-specific vs widespread clusters
- BGC/GCF rarefaction & accumulation curves → is the taxon's biosynthetic space saturated?
- Pangenome openness (Heaps' law α); accessory-genome functional enrichment (eggNOG)
- ARTS resistance-guided prioritization (self-resistance as bioactivity hint)
- cblaster / clinker targeted search + synteny for a specific BGC of interest

### Tier 3 — Idiosyncratic / paper-specific (the long tail)
- Custom prioritization matrices (novelty × quality × resistance × taxonomy, group-weighted)
- BGC-content ↔ metadata association (isolation source, bioactivity, host): Fisher/chi-square, PERMANOVA
- Enzyme-family SSNs, HGT inference, ancestral-state reconstruction of GCF gain/loss

---

## 4. Sub-questions (ordered by distance from the peak question)

| ID | Sub-question | Serves | Distance from peak |
|---|---|---|---|
| SQ1 | Inventory — what / how many BGCs? | describe | Closest |
| SQ2 | Novelty — known vs new? *(PLM side-channel lives here)* | describe/prioritize | Closest |
| SQ5 | Prioritization — which to chase in the lab? | prioritize | Close |
| SQ3 | Distribution — how spread across strains/taxa? | contextualize | Medium |
| SQ4 | Diversity / sampling — how diverse, is it saturated? | contextualize | Medium |
| SQ6 | Genomic context — core vs accessory, resistance, HGT | contextualize | Far |
| SQ7 | Association — do BGCs track phenotype/metadata? | contextualize | Far |

---

## 5. The drift test (decision rule)

The drift risk is per-*framing*, not per-method. Example: pangenome analysis writ large drifts far from the peak question because most of the pan/core genome is housekeeping genes irrelevant to secondary metabolites. It stays under the peak question only when constrained to the BGC-relevant slice ("are *these* BGCs core or accessory?", "which accessory genes co-occur with which GCFs?").

> **Rule:** Every catalogued method must declare how its output feeds back to a BGC or GCF. If it can't, flag it as drift.

---

## 6. Statistics needed (mostly descriptive — good for scope)

- Descriptive: counts, frequencies, per-genome distributions
- Diversity: richness, Shannon, rarefaction / accumulation curves
- Matrix ops: GCF presence/absence → hierarchical clustering, UMAP, heatmaps
- Curve fitting: Heaps' law (pangenome openness)
- Association (Tier 3 only): Fisher / chi-square, correlation, PERMANOVA on distance matrices

No heavy inferential machinery is needed for the core loop. The hard part is the joining and interpretation, not the math.

---

## 7. Open items / next gate

- [ ] Pressure-test and lock the SQ1–SQ7 list
- [ ] Validate the sub-question map with a lab person (which sub-question is their real pain?)
- [ ] Confirm which tier boundary defines the MVP catalog (working assumption: Tier 1)
- [ ] Decide how the drift rule is enforced in the catalog schema
