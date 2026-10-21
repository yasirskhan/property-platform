"""The dormant automatic dispatch-review worker must not enqueue when OFF."""
import asyncio

from app.core.config import settings
from app.jobs.worker import schedule_dispatch_auto_attention


def test_unreleased_dispatch_auto_review_scheduler_never_enqueues(monkeypatch):
    monkeypatch.setattr(settings, "DISPATCH_AUTO_REVIEW_ENABLED", False)
    # A sentinel here intentionally lacks any Redis methods. An accidental
    # job enqueue or connection attempt must fail this regression test.
    result = asyncio.run(schedule_dispatch_auto_attention({"redis": object()}))
    assert result == {"enabled": False}
