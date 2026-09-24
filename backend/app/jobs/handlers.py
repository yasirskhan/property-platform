"""Built-in background job handlers.

Business modules add handlers here or import additional handler modules from
worker.py so registration happens before the worker starts.
"""

from __future__ import annotations

from typing import Any

from app.core.database import SessionLocal
from app.jobs.registry import register_job_handler
from app.services.fraud import refresh_checkout_velocity_cases


@register_job_handler("health.noop")
async def health_noop(payload: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "payload": payload}


@register_job_handler("fraud.refresh")
async def fraud_refresh(_payload: dict[str, Any]) -> dict[str, int]:
    db = SessionLocal()
    try:
        result = refresh_checkout_velocity_cases(db)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
