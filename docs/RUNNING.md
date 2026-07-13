# Running BGCLens — agent and human guide

## Quick-start (local demo, no BGCFlow data needed)

```bash
make install        # uv venv + pip install -e ".[dev,bio,network,llm]"
make test-unit      # 148 unit tests, all offline — should pass in ~10s
make web            # starts http://localhost:8765
```

Open `http://localhost:8765` in a browser. Walk through the four-step wizard using the bundled synthetic project (auto-loaded on startup).

---

## Demo flow (the path judges need to see work)

The canonical demo query:

> **"Find lignocellulose-degrading enzymes from termite gut microbiome suitable for expression in E. coli."**

Step-by-step:

1. **Load project** — click the demo project tile or use `bgclens open <path>`
2. **Choose intent** — select "ordination" or "diversity" from the intent dropdown
3. **Select method** — pick `pcoa` (ordination) or `alpha_diversity` (diversity); the advisor shows why
4. **View result** — inline SVG figure renders; interpretation text appears below
5. **Generate Report** — click the "Generate Report" button; downloads a `.qmd`/HTML report

---

## Run against real BGCFlow data

```bash
make sync                           # pull BGCFlow output from GPU box (see Makefile)
make test                           # unit + integration against Lactobacillus_delbrueckii
```

Or point directly:

```bash
bgclens open /path/to/bgcflow/data/processed/Lactobacillus_delbrueckii
bgclens recommend /path/to/project --intent ordination
bgclens run /path/to/project --method pcoa --output ./results/
bgclens report /path/to/project --run-id <run_id>
```

---

## Integration test env-var gating

| Test file | Gate | What it needs |
|-----------|------|--------------|
| `tests/integration/test_walking_skeleton.py` | none | synthetic fixtures, always runs |
| `tests/integration/test_web_api.py` | none | synthetic fixtures + FastAPI TestClient |
| `tests/integration/test_cli_web_parity.py` | none | synthetic fixtures |
| `tests/integration/test_bgcflow_end_to_end.py` | `BGCFLOW_PROCESSED_DIR` | real BGCFlow output |
| `tests/integration/test_bgcflow_end_to_end.py` | `BGCLENS_RUN_BGCFLOW=1` | full BGCFlow (Linux + Snakemake) |
| `tests/integration/test_llm_goals.py` | `BGCLENS_LLM_ENABLED=true` | live LLM endpoint in `.env` |

```bash
# Run only what's always-safe:
uv run pytest tests/unit tests/integration/test_walking_skeleton.py tests/integration/test_web_api.py tests/integration/test_cli_web_parity.py -q

# Add real data:
BGCFLOW_PROCESSED_DIR=./remote-data/data/processed/Lactobacillus_delbrueckii \
  uv run pytest tests/integration/test_bgcflow_end_to_end.py -q

# Add live LLM:
BGCLENS_LLM_ENABLED=true BGCLENS_LLM_BASE_URL=... BGCLENS_LLM_API_KEY=... \
  uv run pytest tests/integration/test_llm_goals.py -q
```

---

## LLM configuration

Copy `.env.example` to `.env`:

```dotenv
BGCLENS_LLM_ENABLED=true
BGCLENS_LLM_BASE_URL=https://api.openai.com/v1
BGCLENS_LLM_API_KEY=sk-replace-me
BGCLENS_LLM_MODEL=gpt-4o-mini
```

The key is never written to provenance YAMLs. A guard layer strips invented numbers/DOIs.

---

## Agent checklist after any nontrivial change

1. `make lint` — ruff + mypy must pass clean
2. `make test-unit` — all 148 tests must pass
3. Start `make web`, walk the four-step wizard, confirm the changed surface works
4. Run `/agent-review` for a pre-commit persona check
5. Log the session with `/session-log` if working autonomously

---

## Makefile targets reference

| Target | What it does |
|--------|-------------|
| `make install` | create venv + pip install editable with all extras |
| `make test-unit` | unit tests only (fast, always-safe) |
| `make test` | unit + integration (needs `make sync` first for real data) |
| `make lint` | ruff check + mypy |
| `make web` | `bgclens web` at port 8765 |
| `make open` | `bgclens open <PROJECT>` (default: synced Lactobacillus) |
| `make sync` | rsync BGCFlow data from GPU box |
| `make push-src` | push local source TO GPU box |
| `make ssh` | open shell on GPU box |
| `make tunnel` | forward remote UI to localhost |
| `make clean` | remove venv + caches |

---

## 3-minute demo video script

1. (0:00–0:20) `make web` → browser opens → show the four-step wizard
2. (0:20–1:00) Load the Lactobacillus project, pick "diversity", select `alpha_diversity`
3. (1:00–1:40) Result renders — point to the SVG figure, the interpretation text, and the confidence band
4. (1:40–2:20) Click "Generate Report" — open the downloaded HTML, show provenance YAML
5. (2:20–3:00) Show `bgclens recommend` in the terminal for the demo query; show the ranked method list
