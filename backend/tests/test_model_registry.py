from __future__ import annotations

import re
from pathlib import Path

import init_db  # noqa: F401  # imports the canonical model registry
from app.core.database import Base

MODELS_DIR = Path(__file__).resolve().parents[1] / "app" / "models"
TABLENAME_RE = re.compile(r'__tablename__\s*=\s*["\']([^"\']+)["\']')


def test_init_db_registers_every_declared_model_table() -> None:
    declared: set[str] = set()
    for path in MODELS_DIR.glob("*.py"):
        if path.name.endswith(".backup-before-currency"):
            continue
        declared.update(TABLENAME_RE.findall(path.read_text(encoding="utf-8", errors="ignore")))

    registered = set(Base.metadata.tables)
    assert registered == declared, (
        f"Model registry drift. Missing={sorted(declared - registered)} "
        f"Extra={sorted(registered - declared)}"
    )
