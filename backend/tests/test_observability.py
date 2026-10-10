from __future__ import annotations

from pydantic import ValidationError

from app.core.config import Settings, settings
from app.core.observability import capture_frontend_error, init_sentry
from app.routers.observability import ClientErrorIn, report_client_error


def test_sentry_is_inert_without_dsn(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SENTRY_DSN", "")
    assert init_sentry() is False
    assert capture_frontend_error(message="browser failed") is None
    assert report_client_error(ClientErrorIn(message="browser failed")) == {
        "accepted": False
    }


def test_frontend_error_relay_uses_bounded_structured_event(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(settings, "SENTRY_DSN", "https://public@example.invalid/1")

    def fake_capture_event(event):
        captured.update(event)
        return "event-1"

    monkeypatch.setattr(
        "app.core.observability.sentry_sdk.capture_event",
        fake_capture_event,
    )

    result = report_client_error(
        ClientErrorIn(
            message="frontend boom",
            stack="stack line",
            path="/dashboard",
        )
    )

    assert result == {"accepted": True}
    assert captured["message"] == "frontend boom"
    assert captured["tags"] == {"source": "frontend"}
    assert captured["extra"]["path"] == "/dashboard"
    assert captured["extra"]["stack"] == "stack line"


def test_sentry_trace_sample_rate_is_validated() -> None:
    try:
        Settings(
            _env_file=None,
            ENVIRONMENT="development",
            SENTRY_TRACES_SAMPLE_RATE=1.1,
        )
    except ValidationError as exc:
        assert "SENTRY_TRACES_SAMPLE_RATE" in str(exc)
    else:
        raise AssertionError("Expected invalid Sentry sample rate to be rejected")



def test_sentry_does_not_capture_tax_bodies_or_stack_locals(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://public@example.invalid/1")
    monkeypatch.setattr(
        "app.core.observability.sentry_sdk.init",
        lambda **options: captured.update(options),
    )
    assert init_sentry() is True
    assert captured["send_default_pii"] is False
    assert captured["max_request_body_size"] == "never"
    assert captured["include_local_variables"] is False
