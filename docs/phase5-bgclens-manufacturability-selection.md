# Phase 5 — Manufacturability Selection (BGCLens)

**Status:** Draft for review · **Depends on:** Phase 1 SQ5 (prioritization engine), Phase 2–4 (literature harvest) · **Next gate:** confirm chassis panel, retrospective calibration

---

## 1. Goal of Phase 5

Help the researcher decide which BGC/pathway to nominate as the **lead candidate for industrial production via a heterologous host** (E. coli or another chassis). The feature ranks candidates by manufacturability and surfaces the blockers behind the ranking, so a non-expert can reach a defensible shortlist instead of stalling on decision paralysis across BGCFlow's heterogeneous outputs.

**Origin:** external evaluation request (industrial fit) added on top of the discovery workflow.

---

## 2. Architectural decision (locked)

Phase 5 is **not a new subsystem**. It is a **manufacturability weighting profile on the shared SQ5 prioritization engine** from Phase 1.

- SQ5 in *discovery* mode ranks candidates by novelty.
- SQ5 in *manufacturability* mode ranks the same candidates by ease of production.
- Same scorecard engine over candidate BGCs; only the objective (feature weights) is swapped.

**Consequence:** Phase 5 is coupled to Phase 1's engine design. Any change to the SQ5 scorecard schema must accommodate both objective profiles.

---

## 3. The honest boundary (overclaiming firewall for Phase 5)

Genome-based manufacturability is a **comparative prior, not a prediction of success.**

- Reported heterologous-expression success rates run only ~11–32% in large-scale studies; host selection in practice is largely trial-and-error.
- Yield is not reliably predictable from sequence — it depends on cultivation conditions and biological complexity — and lab-scale performance often fails to predict scale-up.

**Design line:** the feature ranks and de-risks candidates and shows *why*. It never emits a verdict like "industrial fit: 87%," never predicts titer, and always exposes the confidence tier behind each score.

---

## 4. Manufacturability decomposition

| Bucket | Question | Genome-derivable? | Role in feature |
|---|---|---|---|
| Value | Is the product worth making? | Partly (class, MIBiG similarity, novelty) | Context flag; market value is external input |
| **Tractability** | Can you clone and express it? | **Mostly yes** | **Defensible core of the score** |
| Process/economics | Can you make it cheaply at scale? | Mostly no | Flagged "external input required" |

The score concentrates on **tractability**, where genome data actually informs the decision.

---

## 5. Ease-of-production index (tiered by rigor)

The index declares which tier it computed at and **degrades gracefully** — it drops to "Tier A only, low confidence" rather than fabricating a number.

| Feature | Source | Tier | Firewall side |
|---|---|---|---|
| Pathway length (n biosynthetic steps) | antiSMASH gene count | A | validity (deterministic) |
| Cluster size / repetitiveness | antiSMASH region | A | validity |
| GC / codon mismatch | genome | A | validity |
| Class tractability + PPTase need | antiSMASH class | A | validity |
| Self-resistance / export genes | ARTS | A | validity |
| Precursor & cofactor demand | pathway exploration → KEGG / BRENDA | B | guidance |
| Max theoretical yield | chassis GEM + FBA | B | guidance |
| Expression precedent (similar class/taxon) | literature harvest (Phase 2–4) | B | guidance |
| Actual titer / rate / yield | external / wet-lab | C | out of scope |

**Tier A** — cheap, always available, fully auditable. Anchored by the empirical rule that yield falls ~exponentially with enzymatic-step count (>30% loss per step), which justifies weighting pathway length heavily.
**Tier B** — model- and literature-dependent; explicitly guidance. Populated by the pathway-exploration enrichment layer (§7).
**Tier C** — walled off; never produced by BGCLens.

---

## 6. Chassis decision + fixed panel

E. coli is often the *wrong* first choice. The recommended chassis is derived from GTDB-Tk taxonomy + BGC class, not assumed:

- Actinobacteria / high-GC / modular PKS-NRPS → *Streptomyces* (S. albus J1074, S. coelicolor M1152/M1154)
- Fungal / P450-heavy → yeast (S. cerevisiae) / Aspergillus
- Small RiPPs / low-GC / short pathways → E. coli viable
- Cyanobacterial / marine → specialized or Streptomyces hosts

**Fixed supported panel (for Tier B):** E. coli, S. albus J1074, S. cerevisiae (+ P. putida optional). Tier B yield estimates are only offered for chassis with a curated GEM; for any other host the feature returns the chassis *recommendation* but marks yield as unavailable. This keeps the feature honest and buildable.

---

## 7. Pathway knowledge exploration = the Tier B enrichment layer

Pulling pathway knowledge on a leading candidate is **not a separate feature** — it is how the Tier B features that the genome can't supply get populated (precursor/cofactor demand, enzyme requirements, prior expression precedent). Runs only on the shortlist (expensive), following the context-decomposed query principle:

- **Nearest characterized pathway** → MIBiG + antiSMASH knownclusterblast (already in BGCFlow)
- **Precursor / cofactor routes** → KEGG / MetaCyc
- **Enzyme demands (P450 redox partners, sugar donors, cofactors)** → BRENDA / Rhea
- **Expression precedent (class × taxon × host × outcome)** → literature harvest — strongest single signal, pure guidance

This is the loop back to Phases 2–4: the paper-harvesting side-channel *is* the precedent engine.

---

## 8. Output shape (scorecard per candidate)

A decomposed scorecard, never a single opaque number:

- Ranked shortlist of candidate BGCs
- Ease-of-production index with per-feature breakdown + tier badges
- Recommended chassis + reasoning
- Blocker flags (high GC, megasynthase, P450-heavy, needs PPTase, exotic precursor)
- Precedent hits (with provenance)
- "What the genome can't tell you" section (titer, real toxicity, market value)
- LLM plain-language narration of the above for non-experts

---

## 9. Firewall mapping

- **Validity side (deterministic, auditable):** all Tier A features, computed from BGCFlow tables with versioned inputs.
- **Guidance side (precedent, provenance-tagged, confidence-banded):** all Tier B features (GEM yield, KEGG/BRENDA demand, literature precedent).
- The score **never merges** the two into one number. The scorecard shows tier and provenance per feature. No literature- or model-derived value may ever write into a validity field.

---

## 10. Technical approach for feature development

### 10.1 Data flow

```
BGCFlow DuckDB / tables
        │  (SQL)
        ▼
[1] Feature extractor  ──► Tier A deterministic features per BGC region
        │
        ▼
[2] Candidate shortlister (SQL/thresholds)  ──► top-N regions only
        │
        ▼
[3] Enrichment (shortlist only)
        ├─ pathway reconstruction  → precursor/cofactor set
        ├─ KEGG/MetaCyc/BRENDA lookups
        ├─ GEM + FBA (chassis panel) → max theoretical yield
        └─ literature precedent harvest (Phase 2 pipeline)
        │
        ▼
[4] Scoring: manufacturability objective profile (config weights on SQ5 engine)
        │
        ▼
[5] Scorecard assembly  ──►  [6] LLM plain-language narration
```

Enrichment runs only on the shortlist to keep GEM/FBA and literature calls affordable.

### 10.2 Component recommendations

- **Feature extractor** — SQL against BGCFlow's DuckDB + a thin pandas layer. Emit a tidy per-region feature table. Keep it pure/deterministic (no network calls) so it stays on the validity side.
- **Class → difficulty / PPTase / chassis-hint lookups** — static, versioned YAML/JSON config tables, not hard-coded. These become **catalog entries** in the BGCLens sense: swappable, human-curated, auditable.
- **Objective profile** — the manufacturability weighting is a config file (weights per feature), a sibling of the discovery-mode profile. Swapping objectives = swapping config, not code.
- **Tier B FBA** — COBRApy with curated GEMs (e.g. E. coli iML1515, an S. albus J1074 GEM, a yeast model such as Yeast8/iMM904, optionally P. putida iJN1463). Add heterologous reactions from pathway reconstruction, set product as objective, read off max theoretical yield. Each GEM is a versioned catalog artifact.
- **Pathway reconstruction** — start light (map antiSMASH domains/extender units → a precursor/reaction set); consider the published BGC→metabolic-pathway auto-reconstruction pipeline if a full GEM insertion is needed.
- **Precedent harvest** — reuse the Phase 2–4 harvester with a decomposed query (BGC class + source taxon + "heterologous expression" + outcome). Store hits with provenance + a confidence band.
- **LLM role — bounded** — used only for (a) narrating the assembled scorecard in plain language and (b) the non-executing discovery track for uncatalogued chassis/methods (surface from literature, human curates in). The LLM never computes the score or writes a validity field. Structured scorecard in → prose out.

### 10.3 Build order (MVP-first, respecting scope discipline)

- **Phase 5.0 (MVP):** Tier A index + chassis heuristic + a precedent "seen / not seen" flag reusing existing MIBiG/knownclusterblast output. No GEM, no external harvest. Fully auditable, ships fast, already useful.
- **Phase 5.1:** add literature precedent harvest (Phase 2 pipeline) → upgrades precedent from a flag to provenance-tagged evidence.
- **Phase 5.2:** add Tier B GEM/FBA for the fixed chassis panel → max-theoretical-yield estimates where a GEM exists.
- **Discovery track (ongoing):** uncatalogued chassis/methods handled non-executing; LLM surfaces candidates from literature for human curation into the catalog.

### 10.4 Testing / validation

- **Retrospective calibration** — run the index over BGCs with *known* heterologous-expression outcomes (from the curated review corpus / MIBiG). Does it rank successfully-expressed clusters higher? Gives a calibration signal without overclaiming.
- **Degradation tests** — confirm the index correctly falls back to "Tier A, low confidence" when enrichment is missing.
- **Firewall tests** — assert no literature- or model-derived value ever writes into a validity field.
- **Objective-swap tests** — confirm the same engine produces both discovery and manufacturability rankings from config alone.

---

## 11. Open items / next gate

- [ ] Confirm the fixed chassis panel (proposed: E. coli, S. albus J1074, S. cerevisiae; P. putida optional)
- [ ] Source/curate the GEMs for the panel (Tier B dependency)
- [ ] Assemble the retrospective calibration set (known expression outcomes)
- [ ] Define the manufacturability weight profile (initial weights, esp. pathway-length penalty)
- [ ] Confirm shortlist size N for the (expensive) enrichment step
