"""Ad-hoc task: run any instruction without writing a task file.

    make prompt P="Open example.com and tell me the page heading"
    uv run bub run prompt --input text="..." [--input start_url=https://...]

Returns the agent's free-text answer (no Output schema). Good for exploring a site before you
turn the process into a real task with outcome codes.
"""
from typing import Optional

from app.tasks.base import BaseTask


class FreePrompt(BaseTask):
    name = "prompt"
    description = "Run a free-text instruction (exploration / one-offs)."
    required_inputs = ["text"]
    optional_inputs = {"start_url": ""}
    # Let browser-use open a URL it finds in the instruction text.
    agent_overrides = {"directly_open_url": True}

    def __init__(self, **inputs):
        super().__init__(**inputs)
        self._start: Optional[str] = self.inputs.get("start_url") or None

    @property
    def start_url(self) -> Optional[str]:  # type: ignore[override]
        return self._start

    def prompt(self) -> str:
        return str(self.inputs["text"])
