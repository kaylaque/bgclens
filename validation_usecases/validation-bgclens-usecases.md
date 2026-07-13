# BGCLens — Validation Procedure (v1)

Purpose: hand this to a bioinformatics reviewer to check that BGCLens ingests, analyzes, and reports BGCFlow outputs correctly and auditably, across two contrasting input shapes.

---

## Use cases

| | **UC-A — Multi-organism panel** | **UC-B — Single-organism, multi-assembly** |
|---|---|---|
| **Input** | 5–7 assemblies, each a *different* organism/species | 5–7 assemblies of *one* organism (strains / assembly versions) |
| **Source** | pick organisms via antiSMASH DB | one taxon, multiple assemblies |
| **Pipeline** | → BGCFlow → BGCLens | → BGCFlow → BGCLens |
| **What it stresses** | taxonomic **breadth**: diverse BGC types, cross-taxa GCF grouping, comparison across species | **consistency**: same BGC called across near-redundant inputs, dereplication, assembly-quality sensitivity |

Both run the same BGCLens checks below; each also has a use-case-specific block.

---

## Validation points (check each)

**1. Ingestion & provenance**
- [ ] BGCFlow output directory ingests without error; all 5–7 inputs present and correctly attributed (assembly → outputs).
- [ ] Provenance (RO-Crate) records which assembly produced which artifact.

**2. Interactive report fidelity (P1)**
- [ ] Re-surfaced report matches BGCFlow's original — no dropped/mangled data.
- [ ] Cluster counts & types match raw antiSMASH output.

**3. Cluster profile correctness**
- [ ] antiSMASH-like profile matches source GBK (domains, cluster type, coordinates).
- [ ] Confidence shown as **bands, not predictions** (wording/color sanity check).
- [ ] (If PLM side-channel on) novelty flags / nearest-neighbors plausible and clearly separated from catalog fields.

**4. Firewall (core principle)**
- [ ] Validity/catalog fields trace to deterministic sources (antiSMASH / MIBiG / Pfam / GTDB) — **not** LLM-written.
- [ ] LLM narration is visually/structurally distinct from catalog facts.

**5. Analysis run**
- [ ] Discovery + manufacturability run per cluster; smoke round (3 clusters) completes.
- [ ] Status board reflects true state (`queued/running/success/failed`).
- [ ] Cross-cluster comparison is correct.

**6. Report (P2)**
- [ ] Each analysis block has method / reasoning / figures / insight / conclusion **+ provenance**.
- [ ] QMD locks: timestamped, immutable, downloadable.

**7. Chat transparency (v3)**
- [ ] Chat answers trace to retrieved data — no fabricated values.
- [ ] Thinking + action trace visible; `@mention` of clusters/sections works.
- [ ] Confidence stays banded in chat.

**8-A. UC-A specific (breadth)**
- [ ] GTDB-Tk taxonomy correct per organism.
- [ ] Cross-taxa GCF grouping is sensible; diverse BGC types surfaced.
- [ ] Comparison is meaningful across species (not forcing false equivalence).

**8-B. UC-B specific (consistency)**
- [ ] Same BGC called consistently across assemblies.
- [ ] Redundancy/dereplication handled; no spurious "novelty" from assembly artifacts.
- [ ] Assembly-quality differences flagged rather than silently averaged.

---

## Report back
For each use case, note: pass/fail per point, any data mismatch vs. raw BGCFlow, and any place narration overstepped into catalog/validity territory (firewall breach) or confidence read as a prediction.
