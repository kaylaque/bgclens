# BGCLens — Chat as Transparent, Observable Interface (Iteration 3)

> Builds directly on `design-bgclens-product-flow-v2.md`. Where v2 established the **persistent chat spine** (v2 §2.6), the **per-cluster parallel run system** (v2 §3), and the **section-addressable report** (v2 §4), this iteration specifies **how the chat exposes its own reasoning and actions** — the transparency/observability layer — and **how it renders researcher-grade content**.
>
> One-line thesis: the chat is not a black box that emits answers. It shows *how it thought*, *what it ran*, and *where each claim came from*, and it renders that in a form a researcher will actually read (mermaid, equations, clean markdown, code/QMD blocks) with reader-vs-researcher depth control.

---

## 0. Relationship to v2

**Carried over unchanged:**
- The chat is persistent and **page-independent** — it stays on the right while the left/main pane swaps between the **interactive report** (v2 §2.2) and the **BGCLens report / rendered QMD** (v2 §4). Changing pages does not reset or move the chat.
- `@mention` targets from the Knowledge Base panel (cluster profiles, datasets, report sections).
- The **run system** (v2 §3): analyses fan out per cluster into parallel sub-agents with a `queued/running/success/failed` status board.

**What Iteration 3 adds:**
1. A **thinking-transparency** layer — the reasoning shown *before* the answer, decomposed into steps.
2. An **action-observability** layer — which sub-agents / tools / retrievals ran, in what order, with what status.
3. A **rich chat renderer** — mermaid, equations, markdown, figures, code/QMD blocks.
4. **Reader-vs-researcher depth control** over how much of the above is shown.

---

## 1. The persistent chat spine (formalized)

- Always present, docked (right pane by default), independent of the active page.
- Multi-turn, context-aware: reads the interactive report, processed datasets, project directory, and — on the report page — the rendered QMD sections.
- The **left/main pane is swappable** under a fixed chat:
  - Interactive report (pre-analysis) →
  - BGCLens rendered report (post-analysis).
- **Role boundary holds (v2 §5):** the chat **narrates and discovers** over retrieved deterministic data. Transparency does not upgrade it to a writer of validity fields.

---

## 2. Transparency — making the *thinking* legible

The answer is preceded by a **decomposed thinking trace**, in the style of a modern assistant that shows its reasoning before the final response — but structured for a scientific workflow rather than as free-form monologue.

### 2.1 Thinking-before-answer, decomposed into steps
- The reasoning is broken into discrete, labeled **steps / functions** (not one undifferentiated block).
- Each step is collapsible; the final answer is always the terminal, most-prominent element.
- Steps map to *what the system is actually doing*: e.g. *interpret question → locate relevant clusters/dataset → retrieve → analyze/compare → compose answer.*

### 2.2 Sub-agent decomposition (the same sub-agents as the run system)
- Where a question spawns work, the thinking trace shows the **sub-agent breakdown** — the same parallel-sub-agent model used by the run system (v2 §3.2), surfaced here as an *observable process* rather than hidden orchestration.
- Each sub-agent node shows its task, status, and result summary. This makes the chat's heavier operations legible in the same visual language as the analysis run board.

> 🔎 Interpretation note: the transcript describes the thinking process "broken down into several functions … preferably broken down onto the sub-agents that are spawned." I've read that as: **the reasoning trace and the sub-agent job graph are the same observability surface**, shown in the chat. Flag if you meant them as two separate things.

### 2.3 Two observability surfaces (added — important distinction)
Keep these conceptually separate; both matter for auditability:

| Surface | Question it answers | Example |
|---------|--------------------|---------|
| **Thinking transparency** | *Why* did it answer this way? | reasoning steps, what it considered |
| **Action observability** | *What* did it actually do? | which retrievals/tools/sub-agents ran, in what order, with what status, over which inputs |

Action observability is the one that carries provenance weight — it's the audit trail. Thinking transparency is for user trust and readability. Don't let a persuasive thinking trace stand in for an actual action trace.

---

## 3. The chat renderer — researcher-grade output

The chat renders rich content inline, not just plain text. Clean markdown is the base; on top of it:

- **Mermaid diagrams** — for flows, method pipelines, cluster relationships.
- **Equations** — LaTeX/MathJax, for methods that are best expressed formally.
- **Figures / charts** — analysis outputs surfaced inline.
- **Code / QMD blocks** — method snippets or the QMD that produced a section.
- **Inline citations / provenance** — links back to the source (paper, repo+commit, dataset, or `@mentioned` report section) for claims that came from retrieval.

This mirrors the **per-analysis output contract** in the report (v2 §3.4): method-as-mermaid-*or*-equation-*or*-concise-prose-*or*-citation. The chat and the report speak the same rendering language, so a section can be discussed in chat in the same form it appears in the report.

> 🔎 Interpretation note: the transcript's "rendered as … code/QMD … in our renderer" and "multi-channel/multi-canvas" I've read as: **the chat renderer supports multiple rich content types (a canvas-like surface), including code/QMD blocks.** Whether those code/QMD blocks are **display-only or executable in-chat is an open decision — see §6.1.** Flag if "multi-channel" meant something else (e.g. multiple parallel chat threads).

---

## 4. Readability — reader vs. researcher depth control

The interface must be readable to a non-expert *and* rigorous for a researcher. Rather than picking one, expose a **depth control**:

- **Reader mode** — clean prose, the key insight, minimal notation; diagrams/equations collapsed by default.
- **Researcher mode** — equations shown, mermaid method diagrams expanded, provenance/citations visible, sub-agent/action trace expanded.
- **Per-content-type preferences** (from the transcript: *"I would love to see diagrams / I would love to see equations"*): let the user pin *"always show equations,"* *"always show method diagrams,"* etc., so their preferred rendering persists across turns and pages.

Default suggestion: reader-mode surface with a one-click expand into researcher depth on any block — so nothing is hidden, but nothing overwhelms.

---

## 5. Observability tie-in with the run system

The chat's action trace (§2.2–2.3) and the run status board (v2 §3.2) are **one observability model, two entry points**:
- During an analysis run, the board shows `queued/running/success/failed` per (analysis × cluster).
- When the chat does heavy work, the same node/status vocabulary shows the sub-agents it spawned.

Benefit: a user learns the observability grammar once. A failed sub-agent looks the same whether it failed in a formal run or inside a chat query, and both are inspectable.

---

## 6. Open decisions & risks

### 6.1 🚩 Executable vs. display-only code/QMD in chat (ties to v2 §6.1)
If the chat renders **runnable** code/QMD, it reopens the auto-execution risk flagged in v2 §6.1. Keep them aligned:
- **MVP: display-only.** Code/QMD blocks render for reading and copy, with provenance; they do not auto-execute from chat.
- Execution stays behind the **run system** with its status board, per-cluster inputs, and (for paper-derived code) the human gate. The chat can *launch* a vetted run; it should not silently *execute arbitrary code* it just wrote in-thread.

### 6.2 Is the thinking trace always-on or toggled?
- Always-on maximizes transparency but can be noisy; toggled respects reader mode.
- Recommendation: **action trace always retained** (audit), **thinking trace collapsed-by-default** and one-click expandable (readability). Never make the *action* trace opt-in — it's the audit record.

### 6.3 Provenance rendering fidelity
- Every retrieval-derived claim in chat should carry a traceable source (paper / repo+commit / dataset / report section). Decide the minimum citation unit and how it renders inline without cluttering reader mode.

### 6.4 "Multi-channel" scope
- Confirm whether this means (a) a multi-type rich renderer / canvas (my reading), or (b) multiple concurrent chat channels/threads, or (c) chat mirrored across dashboard *and* report views. Each is a different build.

---

## 7. Guardrails (cross-cutting principles, applied to the interface)

- **Transparency serves auditability, not overclaiming.** A legible thinking trace must not become a vehicle for confident-sounding claims the retrieval didn't support. Shown reasoning should trace to retrieved deterministic data; where it's discovery/speculation, it's labeled as such.
- **Firewall holds in the renderer.** A method rendered as an equation or mermaid diagram describes a *source* method — it cites/traces, it does not fabricate. Catalog/validity facts and LLM narration remain visually and structurally distinct in chat, same as in the report (v2 §5).
- **Confidence stays banded.** Any confidence surfaced in chat is a banded prior, never a prediction (v2 §5).
- **The audit trail is the product.** Action observability + inline provenance is what makes BGCLens's chat trustworthy to a researcher, and is the throughline connecting Iterations 2 and 3.
