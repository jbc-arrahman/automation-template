"""Per-run trace: one JSON line per run in LOGS_DIR/traces/trace_<date>.jsonl, with every agent
step (url, goal, actions, errors) and the final result. Use it to see WHY a run failed and as
labelled data for improving prompts. A trace must never break a run: every call swallows errors.

Add masking here if your inputs contain personal data.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import time
import uuid
from typing import Any

from app.config import Settings

log = logging.getLogger(__name__)
MAX_TEXT = 2000


def _clip(v: Any) -> Any:
    if isinstance(v, str):
        return v[:MAX_TEXT]
    if isinstance(v, dict):
        return {k: _clip(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clip(x) for x in v]
    return v


class RunTrace:
    def __init__(self, settings: Settings, task_name: str, mode: str, inputs: dict):
        self.settings = settings
        self.enabled = settings.trace_enabled
        self.t0 = time.time()
        self.record: dict[str, Any] = {
            "run_id": uuid.uuid4().hex[:12],
            "started_at": dt.datetime.now().isoformat(timespec="seconds"),
            "task": task_name,
            "mode": mode,
            "inputs": _clip(inputs),
            "events": [],
        }

    @property
    def run_id(self) -> str:
        return self.record["run_id"]

    def event(self, kind: str, **data: Any) -> None:
        if not self.enabled:
            return
        try:
            self.record["events"].append({"t": round(time.time() - self.t0, 2), "kind": kind, **_clip(data)})
        except Exception:
            pass

    async def on_step_end(self, agent) -> None:
        """Hook for Agent.run(on_step_end=...)."""
        try:
            h = agent.history.history[-1] if agent.history.history else None
            if h is None:
                return
            out = h.model_output
            self.event(
                "step",
                n=len(agent.history.history),
                url=getattr(h.state, "url", None),
                goal=getattr(out, "next_goal", None) if out else None,
                actions=[a.model_dump(exclude_none=True) for a in (out.action if out else [])],
                errors=[r.error for r in h.result if r.error],
            )
        except Exception as e:
            log.debug("trace step failed: %s", e)

    def finish(self, **final: Any) -> None:
        if not self.enabled:
            return
        try:
            self.record["duration_sec"] = round(time.time() - self.t0, 2)
            self.record["final"] = _clip(final)
            path = self.settings.logs_dir / "traces" / f"trace_{dt.date.today().isoformat()}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(self.record, default=str, ensure_ascii=False) + "\n")
        except Exception as e:
            log.debug("trace write failed: %s", e)
