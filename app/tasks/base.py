"""BaseTask - the ONE class you subclass to automate a new process.

A task = a prompt (what to do, step by step) + an output schema (what to return) + a few knobs.
Everything else (LLM, browser mode, timeouts, cost log, trace) is handled by app/runner.py.

    class MyTask(BaseTask):
        name = "my_task"
        description = "One line shown by `make tasks`"
        required_inputs = ["url"]
        start_url = "https://example.com"          # opened before the agent starts (optional)
        allowed_domains = ["example.com"]          # the agent cannot leave these (optional)
        Output = MyOutput                          # pydantic model the agent must return

        def prompt(self) -> str:
            return f"1. Open {self.inputs['url']} ... Finish with the structured result."

See docs/CREATING_TASKS.md for the full walkthrough.
"""
from __future__ import annotations

import os
from typing import Any, ClassVar, Optional, Type

from pydantic import BaseModel


class TaskInputError(ValueError):
    pass


class BaseTask:
    # ---- identity ----------------------------------------------------------------------------
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    # ---- inputs ------------------------------------------------------------------------------
    required_inputs: ClassVar[list[str]] = []
    optional_inputs: ClassVar[dict[str, Any]] = {}      # name -> default

    # ---- result ------------------------------------------------------------------------------
    # Pydantic model the agent must finish with. None -> free-text result (history.final_result()).
    Output: ClassVar[Optional[Type[BaseModel]]] = None

    # ---- browser -----------------------------------------------------------------------------
    start_url: ClassVar[Optional[str]] = None           # navigated to before the first LLM step
    allowed_domains: ClassVar[list[str]] = []           # empty -> no restriction
    preferred_mode: ClassVar[Optional[str]] = None      # "installed" | "fresh" | None (use .env)

    # ---- agent -------------------------------------------------------------------------------
    system_rules: ClassVar[str] = ""                    # appended to browser-use's system prompt
    max_steps: ClassVar[Optional[int]] = None           # None -> AGENT_MAX_STEPS
    timeout_sec: ClassVar[Optional[int]] = None         # None -> AGENT_TASK_TIMEOUT_SEC
    use_vision: ClassVar[Optional[bool]] = None         # None -> USE_VISION
    # Any other browser_use.Agent(...) keyword, e.g. {"max_actions_per_step": 3, "flash_mode": True}
    agent_overrides: ClassVar[dict[str, Any]] = {}
    # Secrets the agent may type without the LLM seeing them: {"placeholder": "ENV_VAR_NAME"}.
    # In the prompt write the placeholder (e.g. "x_password"); browser-use substitutes the value.
    sensitive_env: ClassVar[dict[str, str]] = {}

    def __init__(self, **inputs: Any):
        missing = [k for k in self.required_inputs if inputs.get(k) in (None, "")]
        if missing:
            raise TaskInputError(f"Task '{self.name}' needs input(s): {', '.join(missing)} "
                                 f"(pass --input {missing[0]}=...)")
        self.inputs: dict[str, Any] = {**self.optional_inputs, **inputs}

    # ---- hooks you implement / may override --------------------------------------------------
    def prompt(self) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def sensitive_data(self) -> Optional[dict[str, str]]:
        data = {ph: os.getenv(env, "") for ph, env in self.sensitive_env.items()}
        return {k: v for k, v in data.items() if v} or None

    def postprocess(self, output: Any) -> Any:
        """Last chance to validate / normalise the agent's result before it is returned."""
        return output
