# Second Brain Vault

A local, plain-markdown second brain powered by [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview). Every note is a `.md` file — no databases, no plugins the AI needs to care about. Just files, folders, frontmatter, and wikilinks.

## Quick start

```bash
# 1. Clone the repo
git clone <your-repo-url> my-second-brain
cd my-second-brain

# 2. Run the setup script
bash setup.sh
```

The script will:
1. Create `CLAUDE.md` from the template and prompt for your profile
2. Create `index.md` — your wiki's master catalog

## How it works

```
raw/                  ← Drop articles/papers here to ingest
wiki/                 ← LLM-maintained atomic notes (concepts, entities, sources)
_templates/           ← Note format blueprints
journal/              ← Daily captures
```

1. Drop a source (PDF, article, web clip) into `raw/` or `Clippings/`
2. Run `claude` — it will read the source, extract key ideas, and create wiki pages
3. Ask questions — Claude reads the wiki and synthesizes answers with citations
4. Good answers can be filed back as permanent wiki pages

## Folder structure

- `_templates/` — note templates. Read these to understand expected structure.
- `raw/` — inbox for unprocessed source documents
- `Clippings/` — inbox for Obsidian Web Clipper saves
- `raw/processed/` — source documents after Claude processes them (audit trail)
- `wiki/concepts/` — synthesized ideas not tied to a single source
- `wiki/entities/` — people, organizations, tools
- `wiki/sources/` — one summary page per ingested source
- `wiki/comparisons/` — synthesis pages created from queries
- `journal/` — daily notes
- `_attachments/` — binaries (PDFs, images) — not read by Claude

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) (for AI-powered wiki management)
- [Obsidian](https://obsidian.md) (optional — for browsing your wiki visually)

## How this vault differs from a regular Obsidian vault

This vault is designed for **AI-first knowledge management**. A Claude Code agent manages the wiki:
- **Ingests** sources and creates structured notes
- **Links** related concepts across pages
- **Lints** for contradictions and orphans
- **Indexes** the growing knowledge base
- **Synthesizes** answers from existing notes

Your job: drop in sources and ask questions. Claude handles the bookkeeping.

## Examples

The `examples/` directory contains demo wiki pages showing the note format. Delete them once you've seen the format.

## Credits

Built on the [LLM Wiki Pattern](https://agentpedia.codes/blog/karpathy-llm-wiki-idea-file) by Andrej Karpathy.
