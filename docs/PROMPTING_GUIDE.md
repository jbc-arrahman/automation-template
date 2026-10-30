# Prompting Guide: Lessons from Production Automation

When automating complex web applications with `browser-use`, the quality of your task prompt and output schema determines **reliability, speed, and token cost**. These patterns come directly from our production browser automation workloads.

---

## 1. Always End with a `Literal` Outcome Code (`Output` Schema)

Never parse free-text sentences from the LLM to figure out if a task succeeded. Give the agent a strict Pydantic `Output` model whose primary field is a `Literal[...]` union of every possible terminal state:

```python
from typing import Literal
from pydantic import BaseModel, Field

Outcome = Literal[
    "SUBMITTED",            # Happy path
    "ALREADY_DONE",         # Nothing to do (idempotent skip)
    "QUOTA_EXCEEDED",       # Rate-limited by the target site
    "ACCOUNT_BLOCKED",      # Login wall, 2FA prompt, or captcha
    "ITEM_NOT_FOUND",       # Target entity doesn't exist
    "UNCLEAR_AFTER_ACTION", # Clicked, waited, no confirmation appeared in time
]

class MyOutcome(BaseModel):
    outcome: Outcome = Field(description="The single code that describes what happened.")
    evidence: str = Field(
        default="",
        max_length=300,
        description="The exact status or dialog text on the page that proves the outcome.",
    )
```

**Why `evidence` matters:** Asking the model to copy the exact badge/toast text it saw into `evidence` forces it to ground its decision in actual DOM text and gives you instant audit logs without opening screenshots.

---

## 2. Write Numbered Steps with Early-Exit Branches

Structure `prompt()` as a numbered state machine where every failure or skip condition tells the agent to **stop immediately and finish with a specific outcome code**:

```text
Steps:
1. Check the account header. If you see a sign-in page, captcha, or "verify it's you", stop and finish with ACCOUNT_BLOCKED.
2. Search for the item "{item_id}".
   - If "No results found" appears, stop and finish with ITEM_NOT_FOUND.
   - If the status badge already says "Published", stop and finish with ALREADY_DONE. Do not click Publish.
3. Click "Publish" exactly ONCE. Never click it a second time.
4. Wait until the loading spinner disappears (up to 60 seconds):
   - "Published successfully" toast -> finish with SUBMITTED.
   - "Daily limit reached" dialog -> close it and finish with QUOTA_EXCEEDED.
```

---

## 3. Guard Against Double-Clicks ("Click ONCE")

On slow web apps (where a live verification or report takes 30–120 seconds), an LLM may think its click didn't register and click the submit button a second time. Prevent this explicitly in both `system_rules` and the step text:

- **In the step:** `Click "Submit" exactly ONCE. Never click it a second time.`
- **In the wait step right after:** `Wait while the site processes the request. This can take 30 to 90 seconds; keep waiting until the spinner disappears.`

---

## 4. Leave the Tab Tidy When Using Mode 1 (`installed`)

Because Mode 1 keeps Chrome open and reuses the same tab across tasks:
- Set `system_rules` to forbid opening stray tabs or switching accounts:
  ```python
  system_rules = (
      "Work only in the tab that is already open. Never open new tabs. "
      "Never sign out or switch accounts. Wait for spinners and dialogs to finish before acting."
  )
  ```
- Add a final cleanup step in your prompt when modals are involved:
  ```text
  Before finishing, close any open modal/dialog so the page is ready for the next task.
  ```

---

## 5. Multi-Language Resilience

When automating accounts across regions (e.g., Japanese, German, or Spanish UI locales), don't hardcode English-only XPaths. Add one line to `system_rules`:

```python
system_rules = (
    "The interface may be shown in any language (for example Japanese); "
    "understand buttons and status messages by meaning, not only English words."
)
```

---

## 6. Why `directly_open_url=False` is the Default

By default in `browser-use`, if a task prompt contains any `https://...` string, `browser-use` automatically navigates the tab to the first URL it sees before Step 1.

In many workflows (like inspecting a target URL inside an admin dashboard), **the URL in the prompt is data to type into an input box, not a page to navigate to**. That is why [`app/agent_factory.py`](../app/agent_factory.py) sets `directly_open_url=False` and instead uses `BaseTask.start_url` when you genuinely want the browser to open a specific page first.
