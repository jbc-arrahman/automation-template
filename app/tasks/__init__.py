"""Task registry. Every BaseTask subclass in a module of this package is found automatically -
drop a new file into app/tasks/ and it shows up in `make tasks` / `--task <name>`."""
from __future__ import annotations

import importlib
import pkgutil
from typing import Type

from app.tasks.base import BaseTask, TaskInputError

__all__ = ["BaseTask", "TaskInputError", "all_tasks", "get_task"]


def all_tasks() -> dict[str, Type[BaseTask]]:
    found: dict[str, Type[BaseTask]] = {}
    for mod in pkgutil.iter_modules(__path__):
        if mod.name.startswith("_") or mod.name == "base":
            continue
        module = importlib.import_module(f"{__name__}.{mod.name}")
        for obj in vars(module).values():
            if isinstance(obj, type) and issubclass(obj, BaseTask) and obj is not BaseTask and obj.name:
                found[obj.name] = obj
    return dict(sorted(found.items()))


def get_task(name: str) -> Type[BaseTask]:
    tasks = all_tasks()
    if name not in tasks:
        raise KeyError(f"Unknown task '{name}'. Available: {', '.join(tasks) or '(none)'}")
    return tasks[name]
