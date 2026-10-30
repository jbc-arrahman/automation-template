"""Runs ONE task end to end. This is the function to call from your own code:

    from app.runner import run_task
    result = await run_task("hn_top_stories", inputs={"count": 3}, mode="fresh")
    if result.ok: print(result.output)

Lifecycle: budget check -> LLM -> browser (mode 1 or 2) -> agent.run with timeout -> parse the
structured result -> postprocess -> screenshot -> cost log -> trace -> close browser.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional, Type, Union

from pydantic import BaseModel

from app import cost
from app.agent_factory import build_agent
from app.browser import open_browser
from app.config import Settings
from app.llm import PROVIDERS, build_llm
from app.tasks import BaseTask, get_task
from app.trace import RunTrace

log = logging.getLogger(__name__)


@dataclass
class RunResult:
    task: str
    mode: str
    status: str                       # ok | no_result | timeout | error | budget_exceeded
    output: Any = None                # dict (structured) or str (free text)
    error: Optional[str] = None
    steps: int = 0
    duration_sec: float = 0.0
    usage: dict = field(default_factory=dict)
    run_id: str = ""
    screenshot: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_output(task: BaseTask, history) -> Any:
    if history is None:
        return None
    if task.Output is None:
        return history.final_result()
    try:
        parsed = history.get_structured_output(task.Output)
        if parsed is not None:
            return parsed
    except Exception:
        pass
    try:
        return history.structured_output
    except Exception:
        return None


async def _screenshot(browser, settings: Settings, task_name: str, tag: str) -> Optional[str]:
    try:
        d = settings.logs_dir / "screenshots"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{dt.datetime.now():%Y%m%d_%H%M%S}_{task_name}_{tag}.png"
        await browser.take_screenshot(path=str(path))
        return str(path)
    except Exception as e:
        log.debug("screenshot failed: %s", e)
        return None


async def run_task(
    task: Union[str, Type[BaseTask], BaseTask],
    inputs: Optional[dict] = None,
    mode: Optional[str] = None,
    settings: Optional[Settings] = None,
    llm=None,
) -> RunResult:
    settings = settings or Settings.from_env()
    if isinstance(task, str):
        task = get_task(task)
    if isinstance(task, type):
        task = task(**(inputs or {}))
    mode = (mode or task.preferred_mode or settings.browser_mode).lower()
    model = settings.llm_model or PROVIDERS.get(settings.llm_provider, PROVIDERS["google"]).default_model
    trace = RunTrace(settings, task.name, mode, task.inputs)
    t0 = time.time()

    if cost.budget_exceeded(settings):
        msg = f"Daily LLM budget ${settings.max_daily_llm_cost:.2f} reached (spent ${cost.today_cost(settings):.4f})"
        trace.finish(status="budget_exceeded", error=msg)
        return RunResult(task.name, mode, "budget_exceeded", error=msg, run_id=trace.run_id)

    llm = llm or build_llm(settings)
    handle = open_browser(settings, mode, allowed_domains=task.allowed_domains)
    try:
        agent = build_agent(task, handle.browser, llm, settings)
    except Exception:
        await handle.close()
        raise
    max_steps = task.max_steps or settings.max_steps
    timeout = task.timeout_sec or settings.task_timeout_sec

    status, output, error, history = "error", None, None, None
    trace.event("agent.start", model=model, max_steps=max_steps, timeout=timeout)
    try:
        history = await asyncio.wait_for(agent.run(max_steps=max_steps, on_step_end=trace.on_step_end),
                                         timeout=timeout)
        output = _parse_output(task, history)
        if output is None:
            status, error = "no_result", "agent finished without a result"
            errs = [e for e in (history.errors() if history else []) if e]
            if errs:
                error += f" (last error: {str(errs[-1]).splitlines()[0][:200]})"
        else:
            output = task.postprocess(output)
            status = "ok"
    except asyncio.TimeoutError:
        status, error = "timeout", f"agent timed out after {timeout}s"
    except Exception as e:
        status, error = "error", f"{type(e).__name__}: {str(e).splitlines()[0][:300] if str(e) else ''}"
        log.exception("agent run failed")
    finally:
        shot = await _screenshot(handle.browser, settings, task.name, "ok" if status == "ok" else "fail")
        usage = await cost.collect_usage(agent)
        try:
            cost.log_cost(settings, task.name, model, usage, status)
        except Exception as e:
            log.warning("could not write cost log: %s", e)
        try:
            await agent.close()
        except Exception:
            pass
        await handle.close()

    if isinstance(output, BaseModel):
        output = output.model_dump()
    result = RunResult(
        task=task.name, mode=mode, status=status, output=output, error=error,
        steps=history.number_of_steps() if history else 0,
        duration_sec=round(time.time() - t0, 2), usage=asdict(usage), run_id=trace.run_id, screenshot=shot,
    )
    trace.finish(status=status, output=output, error=error, usage=result.usage, screenshot=shot)
    return result
