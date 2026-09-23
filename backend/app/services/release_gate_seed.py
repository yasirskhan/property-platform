"""Seed release gates from Feature Registry metadata without overwriting state."""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.release_gate import ReleaseGate, ReleaseStage


RELEASE_GATE_RE = re.compile(r"\brelease\.[a-z0-9_.]+\b")


def extract_release_gate_keys(registry_text: str) -> list[str]:
    return sorted(set(RELEASE_GATE_RE.findall(registry_text)))


def seed_release_gates(
    db: Session,
    *,
    registry_path: Path,
) -> tuple[int, int]:
    keys = extract_release_gate_keys(registry_path.read_text(encoding="utf-8"))
    existing = {
        key
        for (key,) in db.query(ReleaseGate.key)
        .filter(ReleaseGate.key.in_(keys))
        .all()
    }

    created = 0
    for key in keys:
        if key in existing:
            continue
        db.add(ReleaseGate(key=key, stage=ReleaseStage.HIDDEN))
        created += 1

    db.commit()
    return created, len(keys)
