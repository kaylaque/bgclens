# BGCLens developer Makefile.
#
# The sync/ssh/tunnel targets are meant to be run FROM YOUR LAPTOP; they reach
# out to the GPU box over SSH. The venv/test/web targets run wherever you are.
#
# Override any variable on the command line, e.g.
#     make sync REMOTE_HOST=gpu.example.org SSH_PORT=2222
#     make sync DRY=1              # show what would transfer, move nothing
#     make sync DELETE=1           # mirror exactly (deletes local extras)

# ---------------------------------------------------------------- remote box
REMOTE_USER    ?= kqueenazima
REMOTE_HOST    ?= 10.4.100.106
REMOTE         := $(REMOTE_USER)@$(REMOTE_HOST)
SSH_PORT       ?= 22

REMOTE_REPO    ?= /datadrive/drive_a/kqueenazima/hackathon-lifescience-beams
REMOTE_BGCFLOW ?= /home/kqueenazima/datadrive/bgcflow
REMOTE_RUNDIR  ?= /home/kqueenazima/bgcflow-run

# Where pulled data lands locally.
LOCAL_DATA     ?= ./remote-data

# Web UI port, used by both `web` and `tunnel`.
PORT           ?= 8765

# ---------------------------------------------------------------- local paths
VENV           := .venv
PY             := $(VENV)/bin/python
BGCLENS        := $(VENV)/bin/bgclens

# Project to analyse. Points at the synced copy by default; override to use a
# path on the GPU box directly.
PROJECT        ?= $(LOCAL_DATA)/data/processed/Lactobacillus_delbrueckii

# ---------------------------------------------------------------- rsync setup
SSH_CMD  := ssh -p $(SSH_PORT)
# DRY=1 -> --dry-run, DELETE=1 -> --delete. Both off by default: sync must not
# destroy local work unless you ask for it.
RSYNC_FLAGS := -avzh --partial --progress --human-readable
RSYNC_FLAGS += $(if $(DRY),--dry-run)
RSYNC_FLAGS += $(if $(DELETE),--delete)

# resources/ is 11 GB of antiSMASH + MIBiG databases, rebuilt by `bgcflow run`.
# .snakemake/ holds per-rule conda envs and locks. Neither belongs on a laptop.
RSYNC_EXCLUDES := \
	--exclude 'resources/' \
	--exclude '.snakemake/' \
	--exclude '.venv/' \
	--exclude '__pycache__/' \
	--exclude '*.pyc' \
	--exclude '.pytest_cache/' \
	--exclude '.mypy_cache/' \
	--exclude '.ruff_cache/' \
	--exclude '.git/'

RSYNC := rsync $(RSYNC_FLAGS) $(RSYNC_EXCLUDES) -e "$(SSH_CMD)"

.DEFAULT_GOAL := help
.PHONY: help ssh tunnel sync sync-results sync-run push-src venv install test test-unit lint web open clean clean-remote-data

help: ## Show this help
	@echo "BGCLens — targets (run sync/ssh/tunnel from your laptop)"
	@echo
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "Remote : $(REMOTE):$(SSH_PORT)"
	@echo "Port   : $(PORT)"
	@echo "Project: $(PROJECT)"

# ---------------------------------------------------------------- ssh access
ssh: ## Open a shell on the GPU box, in the repo directory
	@$(SSH_CMD) -t $(REMOTE) 'cd $(REMOTE_REPO) && exec $$SHELL -l'

tunnel: ## Forward the remote BGCLens web UI to localhost (see Port below)
	@echo "Forwarding $(REMOTE):$(PORT) -> http://localhost:$(PORT)  (Ctrl-C to stop)"
	@$(SSH_CMD) -N -L $(PORT):127.0.0.1:$(PORT) $(REMOTE)

# ---------------------------------------------------------------- pull data
sync: sync-results sync-run ## Pull BGCFlow data + run artifacts from the GPU box
	@echo "Synced into $(LOCAL_DATA)/"

sync-results: ## Pull bgcflow/data/ (processed + interim + raw), skipping the 11 GB databases
	@mkdir -p $(LOCAL_DATA)
	$(RSYNC) $(REMOTE):$(REMOTE_BGCFLOW)/data $(LOCAL_DATA)/

sync-run: ## Pull ~/bgcflow-run/ (pipeline logs, figures, provenance)
	@mkdir -p $(LOCAL_DATA)
	$(RSYNC) $(REMOTE):$(REMOTE_RUNDIR)/ $(LOCAL_DATA)/bgcflow-run/

push-src: ## Push local bgclens source TO the GPU box (source only, never data)
	$(RSYNC) --exclude 'remote-data/' ./ $(REMOTE):$(REMOTE_REPO)/bgclens/

# ---------------------------------------------------------------- local dev
$(VENV): pyproject.toml
	@command -v uv >/dev/null || { echo "uv not found: https://docs.astral.sh/uv/"; exit 1; }
	uv venv $(VENV)
	@touch $(VENV)

venv: $(VENV) ## Create the virtualenv (uv, system python)

install: $(VENV) ## Install bgclens with all extras, editable
	VIRTUAL_ENV=$(VENV) uv pip install -e ".[dev,bio,network,llm]"

test-unit: install ## Run unit tests
	$(PY) -m pytest tests/unit -q

test: install ## Run unit + integration tests against the project (see Project below)
	@test -d "$(PROJECT)" || { echo "No project at $(PROJECT). Run 'make sync' first."; exit 1; }
	$(PY) -m pytest tests/unit -q
	BGCFLOW_PROCESSED_DIR="$(PROJECT)" $(PY) -m pytest tests/integration -q

lint: install ## Ruff + mypy
	$(VENV)/bin/ruff check bgclens bgclens_cli bgclens_web
	$(VENV)/bin/mypy bgclens

open: install ## Show the project manifest
	$(BGCLENS) open "$(PROJECT)"

web: install ## Serve the web UI locally (see Port below)
	$(BGCLENS) web --host 127.0.0.1 --port $(PORT) --no-browser

clean: ## Remove venv and caches
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

clean-remote-data: ## Delete the locally synced copy
	rm -rf $(LOCAL_DATA)
