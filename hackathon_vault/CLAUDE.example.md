# Second Brain — Instructions for Claude Code

> This file is loaded automatically at every session.
> Write it for the model, not for yourself. Treat it like onboarding a new hire.

---

## Who I am

I am a __ROLES__ with focus areas in __FOCUS_AREAS__. My goal is to build a connected knowledge base from papers, articles, videos, and ideas I encounter.

## What this vault is

A local, plain-markdown second brain. Every note is a `.md` file. No databases.
No plugins the AI needs to care about. Just files, folders, frontmatter, and wikilinks.

---

## Folder map

```
raw/                  ← INBOX: PDFs go to _attachments/, stubs here.
Clippings/            ← INBOX: Obsidian Web Clipper saves here. Treat same as raw/.
raw/processed/        ← Move source files here after ingesting. Never delete.
wiki/                 ← All permanent atomic notes. Four subfolders by role.
wiki/concepts/        ← Synthesized ideas not tied to a single source.
wiki/entities/        ← People, organizations, tools.
wiki/sources/         ← One summary page per ingested source (papers, articles, videos).
wiki/comparisons/     ← Synthesis pages filed from queries.
wiki/overview.md      ← High-level orientation: vault topic clusters and status.
journal/              ← Daily captures. Format: YYYY-MM-DD.md
_attachments/         ← Binary files (PDFs, images). You do NOT read these directly.
_templates/           ← Note templates. Read these to understand expected structure.
index.md              ← Master list of all wiki/ pages. YOU maintain this.
log.md                ← Append one line per session: date + what you did.
```

**Ingest routing — which subfolder to place new wiki pages in:**

| Page type | Target subfolder |
|---|---|
| Paper, article, video summary | `wiki/sources/` |
| Synthesized concept (no single source) | `wiki/concepts/` |
| Person, organization, tool | `wiki/entities/` |
| Query result filed as note | `wiki/comparisons/` |

---

## Your job each session

**Default behavior unless told otherwise:**

1. Read `log.md` to recall what happened last session
2. Scan `raw/` and `Clippings/` for any unprocessed files
3. For each file in `raw/` or `Clippings/`:
   - Detect type (paper / article / YouTube / PDF stub / misc)
   - Apply the matching template from `_templates/`
   - Extract key ideas → create or update `wiki/` pages
   - Check for contradictions with existing wiki pages; flag them explicitly before writing
   - Add `[[wikilinks]]` to related existing pages
   - Move the source file to `raw/processed/`
4. Update `index.md` — add any new wiki pages
5. Append one line to `log.md`

---

## Query workflow

When asked a question against the wiki:

1. Read `index.md` to identify relevant pages
2. Read those pages
3. Synthesize an answer with `[[wikilink]]` citations to the pages you used
4. If the answer surfaces a useful synthesis (a comparison, a pattern, a resolved tension), offer to file it as a new wiki page (`type: comparison` or `type: concept`, `status: seedling`)

**Search at scale:** When the wiki grows beyond ~100 pages and `index.md` becomes too large to read in one pass, use `qmd` for hybrid BM25/vector search instead of step 1:
```
qmd query "<question>" --json
```
Setup: `npm install -g @tobilu/qmd && qmd collection add ./wiki --name vault`

---

## Lint workflow

When asked to lint or health-check the wiki:

1. Scan all `wiki/` pages for contradictions between pages
2. List pages with no inbound `[[wikilinks]]` (orphans)
3. List concept names mentioned 3+ times across pages but lacking their own wiki page
4. Flag claims in older pages that newer sources have superseded
5. Suggest 2–3 questions worth investigating next

Report findings as a structured list. Do not auto-fix — present the report and ask which items to address.

---

## Note conventions

### Frontmatter (required on every wiki/ note)

```yaml
---
title: "Human-readable title"
type: concept | paper | article | video | person | project | entity | comparison
tags: [tag1, tag2]
date: YYYY-MM-DD
source: URL or filename
related: ["[[Note A]]", "[[Note B]]"]
status: seedling | growing | evergreen
confidence: high | medium | low
---
```

`confidence` means:
- `high` — well-sourced, verified across multiple references
- `medium` — plausible, single source or partially verified
- `low` — unverified extract, needs more sourcing

`status` means:
- `seedling` — raw extract, barely processed
- `growing` — has links, needs more work
- `evergreen` — stable, well-connected, can be cited

### Wikilinks

Always link concept names that have or should have their own wiki page.
Write: `[[Attention Mechanism]]`, not `attention mechanism`.
If the page doesn't exist yet, still write the link — it becomes a stub target.

### File naming

- Wiki pages: title-case, spaces OK → `Transformer Architecture.md`
- Journal: date prefix → `2026-05-20.md`
- Raw clips: auto-named by Web Clipper (don't rename)

### Atomic notes

One idea per wiki page. If a note covers two ideas, split it.
The note answers: **"What is this?"** in 3–5 sentences, then goes deeper.

---

## Template selection logic

| Source type | Clues to detect | Template |
|-------------|----------------|----------|
| Academic paper | arXiv URL, DOI, "Abstract", authors list | `_templates/paper.md` |
| Web article | Blog URL, no abstract, narrative prose | `_templates/article.md` |
| YouTube video | youtube.com URL, transcript-like text | `_templates/youtube.md` |
| PDF stub | `source:` field points to `_attachments/*.pdf` | `_templates/paper.md` or `_templates/article.md` |
| Daily note | File in `journal/` | `_templates/daily.md` |

---

## Graph and query awareness

- Frontmatter fields are queryable via Dataview. Keep them consistent.
- `tags` should use existing tags before inventing new ones. Check `index.md` for the tag list.
- `type` field is used in Dataview dashboards — use only the allowed values above.
- `status: evergreen` notes are candidates for the knowledge graph homepage.

---

## What you must NEVER do

- Do not modify files in `raw/processed/` — they are the audit trail
- Do not delete any file
- Do not create files outside the defined folder structure
- Do not invent sources — if something is unclear, mark it `status: seedling` and flag it
- Do not rewrite a wiki page that already has `status: evergreen` without asking first

---

## Index maintenance

`index.md` format:

```markdown
# Vault Index

Last updated: YYYY-MM-DD

## Stats
- Total wiki notes: N
- Evergreen: N
- Seedlings: N

## By type

### Concepts
- [[Attention Mechanism]] — how transformers focus on relevant tokens #ml #architecture
- [[PARA Method]] — folder structure for second brains #pkm

### Papers
- [[Attention Is All You Need]] — Vaswani et al. 2017 foundational transformer paper #ml

### Articles
<!-- Claude populates this -->

### Entities
- [[Andrej Karpathy]] — ML educator, author of LLM Wiki pattern #person

### Comparisons
<!-- Claude populates this -->

### Videos
<!-- Claude populates this -->

## Tags used
#ml #pkm #architecture #person #writing
```

---

## Session log format

Append to `log.md` at the end of every session:

```
2026-05-20 | Ingested 3 articles, created wiki/Attention Mechanism.md, updated index.md
```
