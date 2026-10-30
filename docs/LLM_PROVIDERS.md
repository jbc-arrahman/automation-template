# LLM Providers & Cost Configuration

[`app/llm.py`](../app/llm.py) provides a single factory (`build_llm(settings)`) that supports every major LLM provider shipped with `browser-use`. Switching models or providers only requires changing `.env`.

---

## Why We Recommend Google Gemini (`LLM_PROVIDER=google`)

In our production browser automation workloads with `USE_VISION=true` (where the agent inspects a screenshot + DOM tree on each step):
- **Gemini Flash (`gemini-3.6-flash` / `gemini-2.5-flash`)** delivered the **lowest cost per completed task** (typically a fraction of a cent per 10-step run) while maintaining strong visual grounding on complex UIs, popups, and non-English pages.
- Prompt token caching works out of the box and is tracked in `logs/api_cost/`.

---

## Supported Providers (`LLM_PROVIDER`)

Set `LLM_PROVIDER` and the corresponding API key in `.env`:

| `LLM_PROVIDER` | Default `LLM_MODEL` | Key Environment Variable(s) | Notes |
|---|---|---|---|
| `google` *(Recommended)* | `gemini-3.6-flash` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Best price/performance for vision |
| `openai` | `gpt-4.1-mini` | `OPENAI_API_KEY` | Also supports `gpt-4.1`, `o4-mini` |
| `anthropic` | `claude-sonnet-4-5` | `ANTHROPIC_API_KEY` | High accuracy, higher token cost |
| `azure` | `gpt-4.1-mini` | `AZURE_OPENAI_API_KEY` + `LLM_BASE_URL` | Set `LLM_BASE_URL` to your Azure endpoint |
| `groq` | `meta-llama/llama-4-maverick-17b-128e-instruct` | `GROQ_API_KEY` | Fast inference |
| `openrouter` | `google/gemini-2.5-flash` | `OPENROUTER_API_KEY` | One key for 100+ models |
| `deepseek` | `deepseek-chat` | `DEEPSEEK_API_KEY` | Set `USE_VISION=false` for text-only models |
| `mistral` | `mistral-medium-latest` | `MISTRAL_API_KEY` | |
| `ollama` | `qwen2.5vl:7b` | *(none)* | Local models; uses `LLM_BASE_URL` or `http://localhost:11434` |
| `openai_compatible` | *(set `LLM_MODEL`)* | `LLM_API_KEY` (optional) | Any vLLM / LM Studio / Together / Fireworks endpoint via `LLM_BASE_URL` |
| `aws` | `anthropic.claude-3-5-sonnet-20240620-v1:0` | Standard AWS env (`AWS_ACCESS_KEY_ID`, `AWS_REGION`) | Install extra first: `uv sync --extra aws` |

> **Tip:** `LLM_API_KEY` in `.env` always takes precedence over provider-specific variables (`GEMINI_API_KEY`, `OPENAI_API_KEY`, etc.), so you can use a single variable name in CI/CD if you prefer.

---

## Vision (`USE_VISION`)

- `USE_VISION=true` *(default)*: Sends a page screenshot alongside the DOM map on every step. Essential for canvas/icon-heavy UIs and verifying visual confirmation dialogs.
- `USE_VISION=false`: Sends only the extracted DOM/accessibility elements. Cuts input tokens and is required when using text-only models (such as `deepseek-chat`).
- You can also override `use_vision = True | False` per task on any `BaseTask` subclass.

---

## Cost Tracking & Daily Budget Guard

Every task execution logs one line to `logs/api_cost/api_cost_<YYYY-MM-DD>.log`:

```text
2026-10-30T11:45:12 | task=hn_top_stories | model=gemini-3.6-flash | calls=3 | tokens=8410 (in=7920 cached=4100 out=490) | cost=$0.000812 | status=ok
```

### Checking Today's Spend
```bash
make cost
# or: uv run bub cost
```

### Setting a Hard Daily Spend Limit
In `.env`:
```ini
MAX_DAILY_LLM_COST=2.00
```
Before starting a run, [`app/runner.py`](../app/runner.py) sums today's cost log. If today's spend is `>= MAX_DAILY_LLM_COST`, `run_task()` refuses to call the LLM and returns `status="budget_exceeded"` immediately.
