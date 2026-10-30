# Step-by-Step Guide: Modifying the Project for Your Own Processes

This boilerplate is structured so that **automating a new business process only requires adding a single file in `app/tasks/`** — you rarely need to touch `app/runner.py`, `app/browser/`, or `app/llm.py`.

---

## 1. Anatomy of a Task

Every process in `app/tasks/` subclasses [`BaseTask`](../app/tasks/base.py) and defines:

1. **Identity & Inputs:** `name`, `description`, `required_inputs`, `optional_inputs`.
2. **Structured Output (`Output`):** A Pydantic `BaseModel` describing the exact data or status code the agent must return when done.
3. **Browser Guardrails:** `start_url`, `allowed_domains`, `preferred_mode` (`"installed"` or `"fresh"`).
4. **Prompt (`prompt(self) -> str`):** Numbered instructions interpolated with `self.inputs`.

Because [`app/tasks/__init__.py`](../app/tasks/__init__.py) auto-discovers every `BaseTask` subclass in `app/tasks/`, creating a file automatically registers it in the CLI (`make tasks`, `make run TASK=...`) and Python API (`run_task("...")`).

---

## 2. Walkthrough: Creating a New Process from Scratch

Suppose you want to automate checking whether an item is in stock on an e-commerce site and extracting its price.

### Step 1: Create `app/tasks/stock_check.py`

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field
from app.tasks.base import BaseTask

# 1. Define explicit outcome codes (prevents ambiguous free-text answers)
StockOutcome = Literal[
    "IN_STOCK",
    "OUT_OF_STOCK",
    "PRODUCT_NOT_FOUND",
    "BLOCKED_OR_CAPTCHA",
]

# 2. Define the structured output schema
class StockCheckResult(BaseModel):
    outcome: StockOutcome = Field(description="The single code that describes the product status.")
    product_title: str = Field(default="", description="The product name shown on the page.")
    price: Optional[str] = Field(default=None, description="Price with currency symbol if visible.")
    evidence: str = Field(
        default="",
        max_length=300,
        description="Exact button or badge text on the page that proves the outcome.",
    )

# 3. Define the task class
class StockCheckTask(BaseTask):
    name = "stock_check"
    description = "Check whether a product URL is in stock and read its price."
    required_inputs = ["url"]
    optional_inputs = {"expected_sku": ""}

    Output = StockCheckResult
    max_steps = 12
    timeout_sec = 180
    system_rules = (
        "Never click 'Add to Cart' or 'Buy Now'. Only inspect the product page and report its state."
    )

    def prompt(self) -> str:
        url = self.inputs["url"]
        sku_note = (
            f"\nVerify that SKU '{self.inputs['expected_sku']}' is selected."
            if self.inputs["expected_sku"]
            else ""
        )
        return f"""Inspect the product page at {url}.{sku_note}

Steps:
1. Open {url} and wait for the main product card to finish loading.
2. If you see a captcha, login wall, or "access denied" screen, stop and finish with BLOCKED_OR_CAPTCHA.
3. If you see a 404 or "Product not found" message, stop and finish with PRODUCT_NOT_FOUND.
4. Read the product title and current price.
5. Check the purchase section:
   - If an "Add to Cart" / "In Stock" state is active -> finish with IN_STOCK.
   - If it says "Out of Stock", "Sold Out", or "Unavailable" -> finish with OUT_OF_STOCK.

Finish with done and the structured result. Put the exact button/status text in evidence.
"""

    def postprocess(self, output: StockCheckResult) -> StockCheckResult:
        # Optional cleanup/normalization in Python after the LLM finishes
        if output.price:
            output.price = output.price.strip()
        return output
```

### Step 2: Verify it appears in the registry

```bash
make tasks
```
You will see `stock_check` listed alongside `hn_top_stories`, `httpbin_form`, and `prompt`.

### Step 3: Run it in Mode 2 (fresh browser) or Mode 1 (installed browser)

```bash
# Mode 2: fresh browser instance
make run-fresh TASK=stock_check INPUT="url=https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"

# Mode 1: installed Chrome on your machine
make run-installed TASK=stock_check INPUT="url=https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
```

---

## 3. Handling Logins, Passwords & Authenticated Sessions

You have **three ways** to handle processes that require being signed in:

### Approach A (Recommended for Google / 2FA sites): Mode 1 (`installed`)
Log in **once by hand** in the persistent Chrome profile, and let your tasks reuse that already-authenticated session all day.
```bash
# 1. Start installed Chrome with its dedicated profile and debug port
make chrome

# 2. In that Chrome window, sign in to your account (complete 2FA once)
# 3. Run your task in Mode 1 — it attaches to the open Chrome without logging in again
make run-installed TASK=my_logged_in_task INPUT="..."
```

### Approach B: Mode 2 with a `persistent` Fresh Profile
If you want a separate `browser-use` browser that still remembers logins across runs:
```ini
# in .env
BROWSER_MODE=fresh
FRESH_PROFILE=persistent
FRESH_PROFILE_NAME=work_account
```

### Approach C: Passing Credentials Safely with `sensitive_env`
If the agent itself needs to type a username/password or API token into a form, **do not interpolate the secret into `prompt()`** (that would send the secret to the LLM and write it into logs). Instead, map a placeholder name to an environment variable via `sensitive_env`:

```python
class PortalLoginTask(BaseTask):
    name = "portal_login"
    start_url = "https://portal.example.com/login"
    allowed_domains = ["portal.example.com"]
    # Maps placeholder used in prompt -> environment variable in .env
    sensitive_env = {
        "portal_user": "PORTAL_USERNAME",
        "portal_pass": "PORTAL_PASSWORD",
    }

    def prompt(self) -> str:
        return """Log in to the portal:
1. Type portal_user into the username field.
2. Type portal_pass into the password field.
3. Click Sign In.
"""
```
`browser-use` replaces `portal_user` and `portal_pass` inside the browser action layer so the LLM never sees the real secret.

---

## 4. Adding Custom Python Actions / Tools (`Tools`)

Sometimes one step in a browser workflow is easier, faster, or safer to execute in deterministic Python (e.g. computing a 2FA TOTP code, calling an internal API, or reading a downloaded file). You can attach custom `browser-use` tools to a task via `agent_overrides`:

```python
from browser_use import ActionResult, Tools
from app.tasks.base import BaseTask

tools = Tools()

@tools.action("Generate current 6-digit 2FA OTP code")
def get_otp_code() -> ActionResult:
    import pyotp, os
    code = pyotp.TOTP(os.environ["OTP_SECRET"]).now()
    return ActionResult(extracted_content=code)

class TwoFactorTask(BaseTask):
    name = "two_factor_login"
    agent_overrides = {"tools": tools}

    def prompt(self) -> str:
        return "1. Sign in. 2. When asked for the 2FA code, call `get_otp_code` and type it in."
```

---

## 5. Calling Tasks from Your Own Python Code, Queue, or API

[`run_task()`](../app/runner.py) is an async function returning a [`RunResult`](../app/runner.py) dataclass. You can call it from a loop, Celery/RQ worker, cron job, or FastAPI endpoint:

```python
import asyncio
from app.config import Settings
from app.llm import build_llm
from app.runner import run_task

async def process_batch(urls: list[str]):
    settings = Settings.from_env()
    # Reuse one LLM client across the whole batch
    llm = build_llm(settings)

    for url in urls:
        res = await run_task(
            "stock_check",
            inputs={"url": url},
            mode="installed",      # or "fresh"
            settings=settings,
            llm=llm,
        )
        print(url, "->", res.status, res.output, f"(${res.usage.get('cost_usd', 0):.5f})")

asyncio.run(process_batch(["https://example.com/item-1", "https://example.com/item-2"]))
```

### `RunResult` fields

| Field | Type | Description |
|---|---|---|
| `res.ok` | `bool` | `True` when `res.status == "ok"` and a valid result was returned |
| `res.status` | `str` | `"ok"` \| `"no_result"` \| `"timeout"` \| `"error"` \| `"budget_exceeded"` |
| `res.output` | `dict \| str \| None` | Dict matching your `Output` Pydantic model (or `str` if `Output = None`) |
| `res.error` | `str \| None` | Error message when `res.ok` is `False` |
| `res.steps` | `int` | Number of LLM steps taken |
| `res.duration_sec` | `float` | Total wall-clock seconds |
| `res.usage` | `dict` | `calls`, `prompt_tokens`, `cached_tokens`, `completion_tokens`, `total_tokens`, `cost_usd` |
| `res.screenshot` | `str \| None` | Path to the end-of-run PNG screenshot in `logs/screenshots/` |
| `res.run_id` | `str` | ID linking to the JSONL trace record in `logs/traces/` |

---

## 6. Checklist Before Moving a New Task to Production

- [ ] **`Output` uses a `Literal[...]` outcome field** covering every failure mode (captcha, logged out, item missing, quota exceeded, throttled) so your caller never has to guess from free text.
- [ ] **`allowed_domains` is set** on the task so a stray link or prompt injection cannot navigate the browser to an external domain.
- [ ] **`start_url` is set** (when applicable) so navigation happens deterministically before the first LLM call.
- [ ] **`max_steps` and `timeout_sec` are tuned** to roughly 1.5x the normal step count so a stuck tab fails fast instead of burning tokens.
- [ ] **Destructive buttons say "click ONCE"** in the prompt (see [PROMPTING_GUIDE.md](PROMPTING_GUIDE.md)).
