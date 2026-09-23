"""Shared pytest setup for the Property Platform backend."""

from __future__ import annotations

import os
from pathlib import Path

# Set deterministic test-safe defaults before application modules import Settings.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("EMAIL_MODE", "console")
os.environ.setdefault("STRIPE_ENABLED", "false")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
