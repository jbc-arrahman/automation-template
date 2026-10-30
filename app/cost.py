"""Token/cost log per run + optional daily budget (MAX_DAILY_LLM_COST).

One line per run in LOGS_DIR/api_cost/api_cost_<date>.log:

  2026-10-30T11:00:00 | task=hn_top_stories | model=gemini-3.6-flash | calls=4 | tokens=12345 ...
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import Settings

log = logging.getLogger(__name__)
_COST_RE = re.compile(r"cost=\$([0-9.]+)")


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


def cost_file(settings: Settings, day: Optional[dt.date] = None) -> Path:
    day = day or dt.date.today()
    return settings.logs_dir / "api_cost" / f"api_cost_{day.isoformat()}.log"


def today_cost(settings: Settings) -> float:
    try:
        text = cost_file(settings).read_text(encoding="utf-8")
    except FileNotFoundError:
        return 0.0
    return sum(float(m) for m in _COST_RE.findall(text))


def budget_exceeded(settings: Settings) -> bool:
    return settings.max_daily_llm_cost > 0 and today_cost(settings) >= settings.max_daily_llm_cost


async def collect_usage(agent) -> Usage:
    try:
        s = await agent.token_cost_service.get_usage_summary()
    except Exception as e:
        log.debug("No usage summary: %s", e)
        return Usage()
    return Usage(
        calls=s.entry_count or 0,
        prompt_tokens=s.total_prompt_tokens or 0,
        cached_tokens=s.total_prompt_cached_tokens or 0,
        completion_tokens=s.total_completion_tokens or 0,
        total_tokens=s.total_tokens or 0,
        cost_usd=float(s.total_cost or 0.0),
    )


def log_cost(settings: Settings, task_name: str, model: str, usage: Usage, status: str) -> None:
    path = cost_file(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (
        f"{dt.datetime.now().isoformat(timespec='seconds')} | task={task_name} | model={model} | "
        f"calls={usage.calls} | tokens={usage.total_tokens} (in={usage.prompt_tokens} "
        f"cached={usage.cached_tokens} out={usage.completion_tokens}) | cost=${usage.cost_usd:.6f} | "
        f"status={status}\n"
    )
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
