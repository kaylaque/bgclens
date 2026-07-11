# 🔬 BGCLens

**Post-processing & interpretation layer for [BGCFlow](https://github.com/NBChub/bgcflow)**

Turn raw BGCFlow pipeline output into analysis-ready results with one command — statistical methods, publication-quality figures, and plain-English interpretation.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-82%20passing-green)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)]()

---

## What it is

BGCFlow produces BGC tables, GCF networks, taxonomy, and quality data. BGCLens picks up where BGCFlow stops: it ingests that processed directory, recommends appropriate statistical methods for your research question, runs them, renders figures, and writes an interpretation — including an optional LLM-enhanced prose pass via any OpenAI-compatible endpoint.

BGCLens is **read-only**. It never invokes BGCFlow and never modifies your data.

---

## Quick start

```bash
# Install (all extras: web UI, bio methods, network, LLM)
pipx install "bgclens[all]"

# Launch the web UI (opens browser automatically)
bgclens web

# Or use the CLI
bgclens open /path/to/bgcflow/data/processed/my_project
bgclens recommend /path/to/project --intent ordination --topic "BGC diversity across clades"
bgclens run /path/to/project --method pcoa --output ./results/
```

---

## How it works

```
BGCFlow processed directory
  │
  ├─ 1. Ingest       → detect pipelines (antiSMASH, BiG-SCAPE, CheckM, GTDB-Tk…)
  ├─ 2. Recommend    → intent validation + literature ranking + compute cost check
  ├─ 3. Run          → execute method with assumption warnings
  ├─ 4. Visualize    → matplotlib SVG + PNG (rendered engine-side)
  ├─ 5. Interpret    → facts → template prose → optional LLM phrasing (guarded)
  └─ 6. Provenance   → bgclens_run_*.yaml (stable hash, round-trips CLI ↔ web)
```

---

## Analysis methods

| Method | ID | Intent | Requires |
|--------|-----|--------|----------|
| Fisher enrichment | `fisher_enrichment` | enrichment | BGC counts + taxonomy |
| PCoA | `pcoa` | ordination | GCF presence/absence |
| PCA | `pca` | ordination | BGC counts |
| PERMANOVA | `permanova` | comparison | GCF presence/absence + groups |
| Alpha diversity | `alpha_diversity` | diversity | BGC counts |
| Hierarchical clustering | `hierarchical_clustering` | clustering | GCF presence/absence |
| Louvain community detection | `louvain_community` | network_structure | GCF network edges |

Methods are declared as YAML entries in `bgclens/catalog/entries/`. Adding a method = YAML file + Python function, no engine changes required.

---

## LLM configuration

Interpretation works without an LLM (template prose only). To enable enhanced phrasing, copy `.env.example` to `.env`:

```dotenv
BGCLENS_LLM_ENABLED=true
BGCLENS_LLM_BASE_URL=https://api.openai.com/v1
BGCLENS_LLM_API_KEY=sk-replace-me
BGCLENS_LLM_MODEL=gpt-4o-mini

# Ollama (local):
# BGCLENS_LLM_BASE_URL=http://localhost:11434/v1
# BGCLENS_LLM_API_KEY=ollama
# BGCLENS_LLM_MODEL=llama3.1:8b
```

Any OpenAI-compatible endpoint works: OpenAI, DeepSeek, Together, Groq, LM Studio, vLLM, LiteLLM.

The API key is never written to provenance YAMLs. A guard layer strips any number, DOI, or accession the LLM invents that wasn't in the source data.

---

## Pointing at BGCFlow output

```bash
bgclens open /path/to/bgcflow/data/processed/mq_saccharopolyspora

# ✔ Project loaded: mq_saccharopolyspora
# Pipelines: antismash, bigscape, bigslice, checkm, gtdbtk, mash
# GCF matrix: 312 GCFs × 26 genomes
# BGC counts: 26 genomes × 6 BGC classes
```

BGCLens auto-detects which BGCFlow pipelines ran by scanning the directory for known output files. DuckDB preferred when present, CSV/TSV fallback otherwise.

---

## Web UI

```bash
bgclens web           # starts at http://localhost:8765
bgclens web --port 9000 --no-browser
```

Four-step wizard: **Load Project → Choose Intent → Select Method → View Result**

- Inline SVG figure rendering
- PNG + SVG download buttons
- LLM-enhanced interpretation (when configured)
- Works fully offline (no CDN dependencies)

---

## Development setup

```bash
git clone https://github.com/your-org/bgclens
cd bgclens
uv sync --extra all --extra dev   # or: pip install -e ".[all,dev]"
uv run pytest tests/ -q
# 82 passed in 16s
```

### Test suite

| Suite | Tests |
|-------|-------|
| Unit (8 modules) | 54 |
| Walking skeleton integration | 11 |
| Provenance parity (CLI ↔ web) | 11 |
| Web API | 6 |
| **Total** | **82** |

Integration tests against real BGCFlow output are env-var gated and skip gracefully on Mac:

```bash
# Run against pre-computed BGCFlow output (any OS)
BGCFLOW_PROCESSED_DIR=/path/to/mq_saccharopolyspora pytest tests/integration/test_bgcflow_end_to_end.py -v

# Full BGCFlow pipeline run (Linux + Snakemake + Singularity required)
BGCFLOW_DIR=/path/to/bgcflow BGCLENS_RUN_BGCFLOW=1 pytest tests/integration/test_bgcflow_end_to_end.py -v -m bgcflow
```

---

## Repository layout

```
bgclens/              # engine — all logic lives here
  adapters/           #   BGCFlow project detection + CSV/DuckDB loaders
  catalog/            #   method YAML entries + Python implementations
  compute/            #   resource probe + compute cost advisor
  core/               #   engine API, session, provenance, config
  interpret/          #   facts → template → LLM phrasing + guard
  literature/         #   OpenAlex client + co-occurrence ranker
  model/              #   canonical pydantic types
  viz/                #   matplotlib renderers → SVG + PNG bytes
bgclens_cli/          # thin Typer CLI (open / recommend / run / web)
bgclens_web/
  api/main.py         #   thin FastAPI wrapper (5 endpoints)
  frontend/           #   self-contained HTML wizard (no build step)
tests/
  fixtures/           #   synthetic demo project (8 genomes, 10 GCFs)
  unit/               #   per-module unit tests
  integration/        #   walking skeleton, parity, web API, BGCFlow e2e
```

---

## License

MIT. See [LICENSE](LICENSE).

---

*Built with [Claude Code](https://claude.ai/code)*
