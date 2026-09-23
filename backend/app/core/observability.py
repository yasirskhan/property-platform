"""Optional Sentry wiring for backend, workers, and browser error relay."""

from __future__ import annotations

from typing import Any

import sentry_sdk

from app.core.config import settings


def init_sentry() -> bool:
    """Initialize Sentry only when a DSN is configured."""
    dsn = settings.SENTRY_DSN.strip()
    if not dsn:
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.SENTRY_ENVIRONMENT.strip() or settings.ENVIRONMENT,
        release=f"property-platform@{settings.APP_VERSION}",
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
    )
    return True


def capture_exception(exc: BaseException) -> str | None:
    if not settings.SENTRY_DSN.strip():
        return None
    return sentry_sdk.capture_exception(exc)


def capture_frontend_error(
    *,
    message: str,
    stack: str | None = None,
    path: str | None = None,
) -> str | None:
    """Relay a bounded browser error into the configured Sentry project."""
    if not settings.SENTRY_DSN.strip():
        return None

    event: dict[str, Any] = {
        "level": "error",
        "message": message,
        "tags": {"source": "frontend"},
        "extra": {
            "stack": stack or "",
            "path": path or "",
        },
    }
    return sentry_sdk.capture_event(event)
