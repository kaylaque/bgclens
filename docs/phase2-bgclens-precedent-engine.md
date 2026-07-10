# Phase 2 — Precedent / Replication Engine (BGCLens)

**Status:** Draft for review · **Feeds:** Phase 3 (validation), Phase 5 (precedent enrichment), the method catalog · **Next gate:** connector primary choice, catalog-reviewer ownership

---

## 1. Goal of Phase 2

Turn the published literature into structured, provenance-carrying **catalog candidates** and **reading lists**: for a given post-analysis need (an SQ1–7 sub-question × output type × organism), find the relevant methods, extract what's needed to judge whether they can be replicated on BGCFlow outputs, and score replication feasibility — without ever asserting catalog validity.

---

## 2. Role in the system

Phase 2 is the **guidance side** of the BGCLens firewall. Everything it emits is precedent: provenance-tagged, confidence-banded, and inert until a human promotes it through the curation gate. It supplies two downstream consumers:

- **Phase 5** — precedent/expression-outcome enrichment for the manufacturability index
- **The method catalog** — candidate methods that, once validated (Phase 3) and curated, become swappable catalog entries

**Firewall rule (non-negotiable):** no Phase 2 output writes into a validity field. Literature provides precedent and reading lists only.

---

## 3. Sub-systems

### 3A · Connector layer — adopt, don't build

Mature aggregator MCP servers already cover the literature side; assembling a connector zoo from scratch is wasted effort.

| Need | Recommended source |
|---|---|
| Aggregated paper search + full text | Scientific-Papers-MCP (PMC, Europe PMC, bioRxiv/medRxiv, CORE, arXiv) or paper-search-mcp (Crossref, OpenAlex, Semantic Scholar, PubMed, Europe PMC, CORE) |
| Metadata backbone + citation graph | OpenAlex |
| Biomedical full text | Europe PMC / PMC |
| Code | GitHub REST/GraphQL API |
| Domain reference | MIBiG, antiSMASH-DB |

**Design:** one aggregator as primary, all other sources behind a thin **adapter interface**, so a source outage degrades gracefully instead of breaking the pipeline. DOI-resolution fallback (Unpaywall → Crossref → Semantic Scholar) is mandatory — OpenAlex open metadata can be incomplete/inconsistent, so never treat a single metadata source as canonical.

### 3B · Extraction schema — keyed to Phase 1

LLM extraction into a **strict JSON schema with per-field provenance** (source sentence/section). Fixed fields plus two BGCLens-specific keys that make a harvest catalog-ready rather than a bare reading list:

- Standard: `title`, `doi`, `github_repo`, `method_name`, `inputs`, `outputs`, `databases_used`, `open_or_closed`, `license`, `replication_feasible`
- BGCLens keys: `sub_question` (which of SQ1–7 it serves), `drift_test_pass` (does its output feed back to a BGC/GCF per the Phase 1 rule)

### 3C · Replication-feasibility scoring

A small **deterministic** scorer over the extracted fields:

- Repo present + runnable? License permits reuse?
- Inputs/outputs compatible with BGCFlow's actual schemas?
- Required databases obtainable?

Output = a *catalog candidate* record. Runnable candidates flow to Phase 3; ones that can't be safely auto-run drop into the **non-executing discovery track** for human review.

### 3D · Context-decomposed query engine

Queries fan out by `(sub_question × output_type × organism)` rather than one monolithic search — per the Phase 1 principle, and the exact entry point Phase 5's precedent enrichment calls into.

---

## 4. Architecture / development guidance

### 4.1 Data flow

```
Need: (SQ, output-type, organism)
        │
        ▼
[A] Connector layer (aggregator MCP + GitHub + domain DBs)
        │  papers + repos
        ▼
[B] LLM extraction  → strict JSON + provenance per field
        │
        ▼
[C] Feasibility scorer (deterministic)
        │
        ├─ runnable  → Phase 3 (validation)
        └─ not runnable → discovery track (human review)
        │
        ▼
Catalog candidate + reading list  (guidance, provenance-tagged)
```

### 4.2 Component recommendations

- **Adapter interface** — a single `SourceAdapter` contract (search, fetch-metadata, fetch-fulltext, resolve-doi) with the primary aggregator as default impl; add GitHub and domain DBs as sibling adapters. Rate-limit per source.
- **Extraction** — LLM with structured-output/JSON-schema enforcement; store records in DuckDB to stay consistent with BGCFlow's own storage. Every field carries a provenance pointer; no field is accepted without one.
- **Feasibility scorer** — pure Python, no network calls, so it stays auditable. Deterministic pass/flag output.
- **Provenance store** — keep the source sentence for each extracted field; this is what a reviewer checks at the gate and what Phase 3 reuses.
- **LLM role — bounded** — extraction and query decomposition only. It never scores validity and never promotes candidates.

### 4.3 Build order (MVP-first)

- **Phase 2.0 (MVP):** primary aggregator connector + extraction schema + feasibility scorer → emit a **reading list** only (no execution). Immediately useful, fully guidance-side.
- **Phase 2.1:** add GitHub + domain-DB adapters; enrich candidates with repo/license signals.
- **Phase 2.2:** wire runnable candidates into Phase 3; turn on context-decomposed fan-out for Phase 5 enrichment.
- **Discovery track:** live from day one — it's just "surface for human, don't execute."

---

## 5. Honest risks

- **Extraction is noisy.** Repos rot, methods are under-specified, reproducibility is genuinely hard. Phase 2's defensible value is *surfacing and structuring with provenance*, not promising auto-replication.
- **Metadata gaps.** Single-source metadata is unreliable; the DOI fallback chain is load-bearing.
- **Scope creep.** Constrain every harvest by SQ1–7 + the drift test — only ingest methods that map to a sub-question and feed back to a BGC/GCF.

---

## 6. Open items / next gate

- [ ] Choose the primary aggregator (Scientific-Papers-MCP vs paper-search-mcp) and lock the adapter contract
- [ ] Resolve **catalog-reviewer ownership** — who staffs the curation gate (this also determines who Phase 3 provenance is *for*)
- [ ] Confirm the extraction schema field list + provenance granularity
- [ ] Decide DuckDB vs separate store for candidate records
