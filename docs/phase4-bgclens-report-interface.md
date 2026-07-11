# Phase 4 — Report-as-Interface (BGCLens)

**Status:** Draft for review · **Consumes:** SQ1–7 engine (P1), method catalog + validation (P2/P3), manufacturability index (P5) · **Decided:** method choice = queued job · **Next gate:** notification transport, walking-skeleton path

---

## 1. Goal of Phase 4

Make the analysis inclusive and transparent for a non-expert lab person: show the reasoning behind each step, let them choose which discovered method gets implemented, run and validate it, show how much it passes, express a confidence measure, and re-interpret the results in that light — all without requiring bioinformatics expertise.

---

## 2. Product thesis: the report IS the interface

Phase 4 is not a UI with a report inside it. It is a **living, regenerable document** the lab person reads. Everything they do: read the document, pick a method, watch a status badge, receive a regenerated document.

This framing makes the two hardest parts of the vision — *transparent* and *inclusive for a non-expert* — structural properties of the artifact rather than features to engineer. A literate document that carries reasoning + code + results + test outcomes + confidence bands in one honest narrative **is** the collapse of BGCFlow's heterogeneous outputs that BGCLens exists to provide.

---

## 3. Three-layer execution model

Compute is decoupled from presentation. The browser never runs a kernel — the real tools (antiSMASH etc.) can't run in-browser anyway, and the heavy compute already lives in the backend.

| Layer | Lifetime | Contents |
|---|---|---|
| Compute | persistent (backend) | Snakemake job runner + Phase 3 validation sandbox. "Run and validate" triggers this. |
| Artifact | persistent, cached | Rendered Quarto report + results per analysis. Survives page close. |
| Session | ephemeral | UI connection + status stream. Torn down on disconnect; cache untouched. |

The caching requirement maps directly: cache the **artifact + results** (persistent), destroy the **session** (ephemeral), surface a **status channel** telling the user which they're looking at.

---

## 4. Quarto as the vehicle

`.qmd` is the right medium, and several requirements are native Quarto features, not things to build:

| Aspiration | Quarto mechanism |
|---|---|
| Transparency (reasoning + code + results together) | Literate `.qmd`: prose + shown code + embedded results |
| Let the lab person choose the method | `params:` — choice = "regenerate with this param," not "execute code" |
| Running cached | `execute: freeze: auto` — caches computation, re-runs only changed chunks |
| Light, easy to deploy | `embed-resources: true` — one self-contained HTML file, any static host |
| Show how much it passes / confidence | Test + confidence panel rendered from Phase 3 results |

The one thing Quarto won't do for you, and the non-negotiable part: **badge every result with its firewall side** (deterministic vs precedent-derived) so a non-expert can see what's a hard call vs a literature-informed suggestion.

---

## 5. Method choice = queued job (decided)

A method selection does **not** block on a live re-render. It enqueues a job; the user is notified when the regenerated report is ready.

```
User picks method (report param)
        │
        ▼
[1] Enqueue job  (input × method × version)
        │
        ▼
[2] Worker: Snakemake run → Phase 3 validation → confidence measure
        │
        ▼
[3] Render Quarto report (freeze cache; hashed key)
        │
        ▼
[4] Notify: report ready  → user opens cached artifact
```

Job states surfaced to the UI: `queued → running → rendering → ready` (plus `cached`, `stale`, `failed`). A small stateful **job/status service** holds this; the page subscribes and shows a badge/toast. On page close the subscription drops; the results cache is untouched. When the user returns, completed jobs are already cached and instantly viewable.

---

## 6. Re-interpretation stays annotating, not rewriting

"Re-interpret results in light of the confidence measure" is the LLM plain-language layer, and it lives on the **guidance side**: it annotates deterministic results with confidence bands and flags which conclusions rest on low-confidence implementations. It never edits validity-side numbers. Annotate, don't overwrite. Skipping this produces a beautiful report that quietly overclaims — the exact failure the product exists to prevent.

---

## 7. Architecture / development guidance

### 7.1 Components

- **Report generator** — stateless: `(params) → self-contained HTML`. No session state; fully reproducible from the param set + cached results.
- **Job/status service** — the only genuinely stateful piece. Queue + worker + job-state store. Budget for it deliberately rather than treating it as UI afterthought.
- **Results cache** — keyed on a hash of `(input × method × version)`. This key's correctness is the subtle engineering (see risks).
- **Notification transport** — SSE or polling for in-session badges; an out-of-session channel (email/webhook) for "report ready" when the page was closed.
- **Control shell** — thin: renders the current report, exposes the method picker, subscribes to status. No compute.
- **LLM role — bounded** — re-interpretation narration only, guidance-side, badged. Never edits validity numbers, never executes.

### 7.2 Priority ordering

| Tier | What | Effort |
|---|---|---|
| **P1 — first** | Transparent Quarto report: reasoning + shown code + results + test/confidence panel, firewall-badged. Self-contained HTML + persistent results cache (`freeze` + hashed key). | Low–medium |
| **P2 — next** | Method-choice → enqueue job. Job/status service + states + notifications. Ephemeral session teardown. Bounded LLM re-interpretation. | Medium |
| **P3 — defer** | Live in-browser execution. If ever built, scope to lightweight *illustrative* snippets only (quarto-live / Pyodide / WebR), never the heavy pipeline. | High |

### 7.3 First build — walking skeleton

Realize the whole vision on one narrow path before generalizing across SQ1–7:

> one real analysis → one report (reasoning + code + results + confidence panel + firewall badges) → one method choice that enqueues a job → one "ready" notification → the regenerated cached report.

This de-risks the real open question, which is not technical: *does a regenerable, provenance-badged report actually reduce a lab person's decision paralysis?* The skeleton is the cheapest way to put that in front of a real user — feeding directly into the queued user-interview validation.

---

## 8. Honest risks

- **Cache-key correctness.** The key must hash `(input × method × version)`. Get it wrong and you serve stale results under a confident-looking confidence band — the worst failure mode for this product. This, not the Quarto rendering, is the hard part.
- **Overclaiming via annotation.** The confidence measure is a banded prior on alignment, not proof. Present it as such; keep it guidance-side.
- **Notification reliability.** Because choice is a queued job, "report ready" must actually reach a user who closed the page — the out-of-session channel is load-bearing, not optional.

---

## 9. Open items / next gate

- [ ] Choose the notification transport (in-session SSE/polling + out-of-session email/webhook)
- [ ] Lock the cache-key hashing scheme (`input × method × version`) and staleness rules
- [ ] Confirm the walking-skeleton analysis + method to build against
- [ ] Confirm firewall-badge design in the report (deterministic vs precedent visual language)
- [ ] Resolve catalog-reviewer ownership (shared with P2/P3) — determines who curates methods offered in the picker
