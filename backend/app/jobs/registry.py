"""In-process registry of durable job handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


JobHandler = Callable[[dict[str, Any]], Awaitable[Any]]
_HANDLERS: dict[str, JobHandler] = {}


def register_job_handler(name: str):
    key = name.strip()
    if not key:
        raise ValueError("job handler name is required")

    def decorator(func: JobHandler) -> JobHandler:
        if key in _HANDLERS and _HANDLERS[key] is not func:
            raise ValueError(f"job handler already registered: {key}")
        _HANDLERS[key] = func
        return func

    return decorator


def get_job_handler(name: str) -> JobHandler | None:
    return _HANDLERS.get(name.strip())


def registered_job_names() -> tuple[str, ...]:
    return tuple(sorted(_HANDLERS))
