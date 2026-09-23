"""Built-in background job handlers.

Business modules add handlers here or import additional handler modules from
worker.py so registration happens before the worker starts.
"""

from __future__ import annotations

from typing import Any

from app.jobs.registry import register_job_handler


@register_job_handler("health.noop")
async def health_noop(payload: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "payload": payload}
