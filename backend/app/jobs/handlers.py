"""Built-in background job handlers.

Business modules add handlers here or import additional handler modules from
worker.py so registration happens before the worker starts.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.database import SessionLocal
from app.jobs.registry import register_job_handler
from app.services.fraud import refresh_checkout_velocity_cases
from app.services.recurring_journal_entries import post_due_recurring_journal_entries


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


@register_job_handler("accounting.recurring_journal_entries.post_due")
async def recurring_journal_entries_post_due(
    payload: dict[str, Any],
) -> dict[str, int]:
    raw_as_of = str(payload.get("as_of") or date.today().isoformat())
    as_of = date.fromisoformat(raw_as_of)
    db = SessionLocal()
    try:
        return post_due_recurring_journal_entries(db, as_of=as_of)
    finally:
        db.close()
