# BGCLens — Product & Flow Design (Iteration 2)

> Scope of this iteration: remap the UI/UX and product flow around a **two-page dashboard** where a **multi-turn chat** sits side-by-side with an interactive report / processed dataset, and where "analysis" becomes a first-class, auditable, per-cluster workflow that terminates in a **locked, provenance-carrying QMD report**.
>
> This is a design/flow spec, not an implementation plan. Open decisions and risks are collected at the end.

---

## 0. What changed from Iteration 1 (the core reframe)

1. **Kill the redundant re-render.** BGCFlow already ships an interactive report. Re-rendering it into *another* interactive Quarto report duplicates work and confuses provenance. Iteration 2 splits the two clearly:
   - **Page 1** surfaces BGCFlow's *existing* interactive report (embedded/linked) plus a distilled **summary + narrative** over it — not a re-render.
   - **Page 2** is reserved for the **new** analyses BGCLens actually produces (the rendered QMD).
2. **Chat becomes the spine, not a side feature.** A persistent multi-turn chat can read the interactive report, the processed dataset, and everything in the project directory, and can be pointed at specific report sections / cluster profiles via `@mention`.
3. **Analysis becomes a real job system.** Chosen analyses run per-cluster, in parallel sub-agents, with per-process loading states (queued / running / success / failed), then reduce to a single narrated summary.
4. **The final report is immutable.** Once rendered, the QMD is locked, timestamped, and (proposed) wrapped in RO-Crate. No post-hoc editing — that is the provenance guarantee.

---

## 1. Information Architecture

Two primary pages, one persistent chat, forward/back navigation, always able to return Home.

| Page | Name | Role |
|------|------|------|
| **P1** | **Dashboard / Home** | Ingest project → view interactive report + cluster profiles → pick analyses (predefined or paper-derived) → launch runs. Chat side-by-side. |
| **P2** | **BGCLens New Report** | Rendered, locked QMD of the analyses that were run. Chat side-by-side, section-addressable via `@mention`. |

**Persistent left panel (both pages): Features / Knowledge Base.** Lists the addressable objects the chat can reference (interactive report, cluster profiles, processed datasets, analysis outputs, report sections). These are the `@mention` targets.

```
┌──────────────────────────────────────────────────────────┐
│  [P1 Dashboard]  [P2 New Report]        project: <name>   │
├───────────────┬──────────────────────────┬───────────────┤
│  FEATURES /   │   INTERACTIVE REPORT      │               │
│  KNOWLEDGE    │   / RENDERED QMD          │   MULTI-TURN  │
│  BASE         │   (view + cluster         │   CHAT        │
│  (@mention    │    profiles)              │   (reads      │
│   targets)    │                           │   report +    │
│               ├──────────────────────────┤   dataset +   │
│               │   ANALYSIS OPTIONS        │   directory)  │
│               │   (multi-tick + paper     │               │
│               │    search)                │               │
└───────────────┴──────────────────────────┴───────────────┘
```

---

## 2. Page 1 — Dashboard / Home

### 2.1 Project ingestion
- User inputs the **directory path** of their BGCFlow project.
- BGCLens also mounts its own **processes directory** (the post-analysis outputs it manages).
- On load, BGCLens indexes what's available: interactive report, processed datasets, cluster set, and any prior BGCLens runs.

### 2.2 Interactive Report (view, not re-render)
- Surface BGCFlow's existing interactive report side-by-side with the chat.
- Add a **distilled summary + narrative** layer on top (one story, not a second report).
- The chat can read the report and answer questions grounded in it.

### 2.3 Cluster Profile (antiSMASH-like)
- antiSMASH-style profile UI per cluster: domains, cluster type, core biosynthetic genes.
- Show a **banded confidence** indicator per cluster.
  - ⚠️ **These are banded priors, not predictions.** Display as bands (e.g. high / medium / low / novel-candidate), never as a probability of "correctness." Wording and color must not imply a score the pipeline didn't produce.
  - If the PLM novelty side-channel (`bgc_novelty_retrieval.tsv`) is wired in, the "novel-candidate" band is where its nearest-neighbor distance / novelty flag surfaces — as a *retrieval-derived prior*, clearly separated from deterministic catalog fields.
- Support viewing **multiple cluster profiles** side-by-side / switchable.

### 2.4 Analysis Options (multi-select)
Two families, both **multi-tickable** (select several, or "run all"):

1. **Predefined analyses** — currently the two carried over:
   - **Discovery** analysis
   - **Manufacturability** analysis (Danisma / Phase 5)
   - (room to add more predefined post-analyses over time)
2. **Paper-derived analyses** — produced by Paper Search (§2.5).

Every selectable analysis must satisfy the **drift test**: it has to trace back to a BGC or GCF. Options that can't be anchored to a cluster/GCF are not offered.

### 2.5 Paper Search
Flow:
1. User enters **topic / keywords**.
2. Retrieve **top 3 relevant papers**.
3. For each, extract a concise triple: **purpose of analysis → method → short result.**
4. From those, generate **multiple analysis options** (multi-tickable).
5. When an option is chosen, the system:
   - re-reads the paper for method detail,
   - locates the paper's **GitHub / source** (extract from paper; web-search for the relevant repo/source if not linked),
   - assembles the analysis with the run inputs (**clusters, processed dataset**),
   - proceeds to **Run Analysis** (§3).

> 🚩 **This is the highest-risk part of the design — see §6.1.** Auto-writing and auto-executing code pulled from arbitrary repositories directly conflicts with BGCLens's auditability/firewall guarantees. Recommend a bounded MVP form (spec + vetted adapters + human gate) rather than free-form codegen-and-run.

### 2.6 Chat (multi-turn, context-aware)
- Reads: interactive report, processed datasets, everything in the project directory, and (on P2) the rendered report sections.
- `@mention` any Knowledge Base object (a cluster profile, a dataset, a report section) to scope the question.
- **LLM role boundary:** the chat **narrates and discovers** over retrieved deterministic data. It does **not** write or score validity fields, and it does not silently invent values not present in the retrieved context. Answers should be traceable to what was retrieved.

---

## 3. Analysis Execution (the run flow)

Triggered when the user launches the ticked analyses. This is the part that replaces "chunk-out-of-result" with a real job pipeline.

### 3.1 Per-cluster fan-out
- Each analysis runs **per cluster**.
- User chooses **how many clusters** to run (with the cost trade-off shown).
- Default **smoke round = 3 clusters** to bound compute during iteration.

### 3.2 Parallel execution + status UX
- Spawn **parallel sub-agents**, one unit of work per (analysis × cluster) or per analysis, as appropriate.
- **Loading breakdown:** every process shows live status — `queued / running / success / failed` — and which method has completed. Model this as a small DAG/job board, not a single spinner.
- Each analysis renders into its own **QMD block**.

### 3.3 Reduce to one narrated summary
- After the parallel blocks complete, a **single LLM inference** composes the top-level summary/story.
- ⚠️ The summary **narrates** the per-analysis outputs; it must not overwrite, re-score, or fabricate results. Per-analysis provenance stays intact underneath the summary.

### 3.4 Per-analysis output contract
Each analysis block in the report contains:
- **Method** — expressed as a mermaid diagram *or* equation *or* concise prose *or* a citation link to the source paper (whichever fits).
- **Reasoning** — why this method, on this input.
- **Figures / charts.**
- **Analysis insight** — the point(s) that matter.
- **Conclusion.**
- **Provenance** — source paper / repo (+ commit), inputs used (which clusters, which dataset), method version. *(added — see §5)*

### 3.5 Cross-cluster comparison
- The report includes a **comparison across all run clusters** (side-by-side view of the same analysis across clusters).

---

## 4. Page 2 — BGCLens New Report

### 4.1 Rendered QMD
- The new page is a **rendered QMD** — render already done during the run; the page just "explodes"/expands the completed blocks.
- Content is chunked into addressable sections: **Analysis A, Analysis B, Analysis C, Manufacturability, …**, plus the cross-cluster comparison and the top-level summary.

### 4.2 Immutability & locking (provenance)
- The QMD can be **downloaded** or **locked**.
- On lock, the cache QMD is renamed to `timestamp_project` and made **not changeable**.
- **Recommended:** wrap the locked report + its inputs in **RO-Crate** so the report, the datasets it consumed, the methods, and the run metadata travel together and are independently verifiable. *(added)*

### 4.3 Chat side-by-side
- Same persistent chat, now able to reference **report sections** directly.
- Because sections already live as QMD blocks, `@mention` just points the chat at a block (e.g. `@Analysis B`, `@Manufacturability`) to ask scoped questions.

---

## 5. Cross-cutting principles (carried forward, applied here)

- **Validity / precedent firewall.** Deterministic catalog data (antiSMASH HMMs, MIBiG, Pfam, GTDB-derived facts) stays strictly separated from literature-derived and LLM-generated content. Validity fields are never LLM-written. In the UI this means catalog facts and narration/discovery are visually and structurally distinct.
- **Confidence = banded priors, never predictions.** Applies to §2.3 cluster confidence and any PLM-derived novelty flags.
- **Bounded LLM roles.** Narration + discovery only. No scoring, no writing validity fields, no fabricating values absent from retrieved context.
- **Provenance is a feature, not a footnote.** Immutable QMD + RO-Crate + per-analysis source/commit/input capture. This is what differentiates BGCLens from "an LLM that runs some scripts."
- **MVP-first / validate before building.** Bound scope to what can be validated with users before it's built (esp. §6).

---

## 6. Open decisions & risks

### 6.1 🚩 Paper-search auto-codegen-and-run (highest risk — needs scoping before build)
"LLM writes the code from an arbitrary repo and runs it" undercuts the core promise (auditability, reproducibility, firewall). Free-form, auto-executed code from unvetted sources is where transparency quietly dies. Proposed bounded path for MVP, in increasing capability:

1. **Extract-and-plan only.** Paper Search returns the purpose/method/result triple + the located repo link + a *proposed* analysis spec. No execution. Human reads and decides. (Safest; probably the right MVP.)
2. **Vetted method adapters.** A curated set of BGC-relevant analysis adapters; paper-derived options map onto an existing adapter rather than generating arbitrary code. Novel methods are queued for review, not auto-run.
3. **Sandboxed + gated execution.** If code is generated/run, it happens in a sandbox, with a **human review gate**, full capture of repo+commit+inputs, and the generated code stored as part of provenance. Never on the auditable critical path without the gate.

Decision needed: which of 1/2/3 is the iteration-2 target. Recommendation: **ship (1), design toward (2).**

### 6.2 Catalog-reviewer ownership (still open)
Who staffs the human curation/review gate — including the new review gate in 6.1(2/3). Unresolved across phases; this iteration adds another place it bites.

### 6.3 Standalone vs. BGCFlow-companion (still open)
This iteration leans hard **companion**: it ingests BGCFlow outputs and re-surfaces BGCFlow's report. Worth making that positioning explicit, or deciding to abstract the ingest layer if standalone is still on the table.

### 6.4 MVP scope questions
- Which **BGCFlow output type + analysis intent** causes the sharpest user pain? That should set what P1 optimizes for first (from the interview guide — validate before coding).
- How many **predefined analyses** at MVP — just Discovery + Manufacturability, or one more?
- Is Paper Search in the MVP at all, or is the MVP just "ingest → view → run the 2 predefined analyses per cluster → locked report," with Paper Search as the next iteration?

---

## 7. Suggested MVP cut (proposal, for validation)

A vertical slice that exercises the whole spine without the risky bits:

1. **Ingest** project directory (§2.1).
2. **View** BGCFlow interactive report + cluster profiles with banded confidence (§2.2–2.3).
3. **Pick** from the two **predefined** analyses, multi-tick (§2.4) — *Paper Search deferred*.
4. **Run** per-cluster (smoke round = 3), parallel sub-agents, live status board (§3.1–3.3).
5. **Produce** locked, timestamped, RO-Crate-wrapped QMD report with per-analysis provenance + cross-cluster comparison (§4).
6. **Chat** side-by-side with `@mention` over report sections and dataset (§2.6, §4.3).

Paper Search (§2.5) and any codegen enter only after (a) the spine is validated and (b) 6.1 is decided.
