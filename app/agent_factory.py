"""Agent factory - builds a browser_use.Agent with the defaults that proved safe in production.

Production defaults and why:
  max_actions_per_step=1   one action, then look again - fewer "clicked the wrong thing" chains
  max_history_items=6      shorter context -> cheaper, and old steps rarely matter
  use_judge=False          no second LLM pass grading the run (cost); your outcome code is the verdict
  directly_open_url=False  a URL inside the task text is DATA, not "go there now"
  calculate_cost=True      token/cost summary for app/cost.py
Every one of these can be overridden per task with BaseTask.agent_overrides.
"""
from __future__ import annotations

from typing import Any

from browser_use import Agent, Browser

from app.config import Settings
from app.tasks.base import BaseTask

DEFAULT_AGENT_KWARGS: dict[str, Any] = {
    "max_actions_per_step": 1,
    "max_history_items": 6,
    "use_judge": False,
    "directly_open_url": False,
    "calculate_cost": True,
    "enable_signal_handler": False,
}


def build_agent(task: BaseTask, browser: Browser, llm, settings: Settings, **extra: Any) -> Agent:
    kwargs: dict[str, Any] = {
        **DEFAULT_AGENT_KWARGS,
        "max_failures": settings.max_failures,
        "use_vision": settings.use_vision if task.use_vision is None else task.use_vision,
    }
    if task.Output is not None:
        kwargs["output_model_schema"] = task.Output
    if task.system_rules:
        kwargs["extend_system_message"] = task.system_rules
    if task.start_url:
        kwargs["initial_actions"] = [{"navigate": {"url": task.start_url, "new_tab": False}}]
    secrets = task.sensitive_data()
    if secrets:
        kwargs["sensitive_data"] = secrets
    kwargs.update(task.agent_overrides)
    kwargs.update(extra)
    return Agent(task=task.prompt(), llm=llm, browser=browser, **kwargs)
