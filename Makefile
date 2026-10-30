# ============================================================================
# browser-use Boilerplate — Makefile
# Supports both Native (uv) and Docker workflows.
# Run `make help` to see all commands.
# ============================================================================

SHELL := /bin/bash
UNAME_S := $(shell uname -s)

TASK ?= hn_top_stories
MODE ?=
INPUT ?=
P ?=
PROFILE ?= Default

# Convert INPUT="k1=v1 k2=v2" into `-i k1=v1 -i k2=v2`
INPUT_FLAGS := $(foreach pair,$(INPUT),-i $(pair))
MODE_FLAG := $(if $(MODE),--mode $(MODE),)
HEADLESS_FLAG := $(if $(HEADLESS),--headless,)

ifeq ($(UNAME_S),Linux)
	COMPOSE_INSTALLED := docker compose -f docker-compose.yml -f docker-compose.linux.yml
else
	COMPOSE_INSTALLED := docker compose
endif

.PHONY: help setup install-browser doctor tasks run run-installed run-fresh prompt \
        chrome chrome-stop chrome-status copy-profile cost test test-browser lint \
        docker-build docker-run docker-run-installed docker-vnc docker-shell clean

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m [TASK=name] [INPUT=\"k=v ...\"] [MODE=installed|fresh]\n"} \
		/^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)

##@ Setup (Native with uv)
setup: ## Install Python dependencies with uv and create .env if missing
	uv sync
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example — set your GEMINI_API_KEY in .env")

install-browser: ## Download Playwright's standalone Chromium for Mode 2 (fresh)
	uvx playwright install chromium

doctor: ## Check API key, installed Chrome, Mode 2 browser, and CDP port
	uv run bub doctor

##@ Running Tasks (Native)
tasks: ## List all available tasks and their inputs
	uv run bub tasks

run: ## Run a task (e.g. make run TASK=hn_top_stories INPUT="count=5" MODE=fresh)
	uv run bub run $(TASK) $(MODE_FLAG) $(HEADLESS_FLAG) $(INPUT_FLAGS)

run-installed: ## Run a task in Mode 1 (installed Chrome on device)
	uv run bub run $(TASK) --mode installed $(HEADLESS_FLAG) $(INPUT_FLAGS)

run-fresh: ## Run a task in Mode 2 (fresh browser instance)
	uv run bub run $(TASK) --mode fresh $(HEADLESS_FLAG) $(INPUT_FLAGS)

prompt: ## Run an ad-hoc free-text instruction: make prompt P="Open example.com and read the title"
	@test -n "$(P)" || (echo "Pass P=\"your instruction\""; exit 1)
	uv run bub run prompt $(MODE_FLAG) $(HEADLESS_FLAG) -i "text=$(P)"

##@ Mode 1 Helpers (Installed Chrome)
chrome: ## Launch installed Chrome with CDP port open (log in once, reuse all day)
	uv run bub chrome start

chrome-stop: ## Stop the installed Chrome launched by `make chrome`
	uv run bub chrome stop

chrome-status: ## Check whether a Chrome is answering on CDP_PORT
	uv run bub chrome status

copy-profile: ## Copy an everyday Chrome profile into ./profiles/installed (PROFILE="Default")
	uv run bub copy-profile --profile "$(PROFILE)"

##@ Running Tasks (Docker)
docker-build: ## Build the Docker image (includes Chromium + Xvfb + noVNC)
	docker compose build bot

docker-run: ## Run a task inside Docker in Mode 2 (fresh headless Chromium)
	docker compose run --rm bot bub run $(TASK) --mode fresh --headless $(INPUT_FLAGS)

docker-run-installed: ## Run inside Docker in Mode 1 (attaches to host Chrome; run `make chrome` on host first)
	$(COMPOSE_INSTALLED) run --rm bot-installed bub run $(TASK) --mode installed $(INPUT_FLAGS)

docker-vnc: ## Run inside Docker with headed Chromium + live view at http://localhost:6080/vnc.html
	docker compose run --rm --service-ports -e ENABLE_VNC=true bot bub run $(TASK) --mode fresh --headed $(INPUT_FLAGS)

docker-shell: ## Open an interactive shell inside the container
	docker compose run --rm --entrypoint bash bot

##@ Logs, Tests & Quality
cost: ## Print today's LLM token spend
	uv run bub cost

test: ## Run fast unit tests (no browser, no LLM calls)
	uv run pytest -m "not browser and not llm"

test-browser: ## Run browser smoke tests for Mode 1 & Mode 2 (starts real browsers, no LLM calls)
	uv run pytest -m browser

lint: ## Run ruff linter
	uv run ruff check app tests

clean: ## Remove temp caches (keeps profiles/ and logs/)
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
