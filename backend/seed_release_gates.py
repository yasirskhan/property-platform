"""Seed missing release gates from docs/FEATURE_REGISTRY.md.

Existing rows are never overwritten. Newly discovered gates start HIDDEN.
"""

from pathlib import Path

from app.core.database import SessionLocal
from app.services.release_gate_seed import seed_release_gates


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = PROJECT_ROOT / "docs" / "FEATURE_REGISTRY.md"


def main() -> None:
    db = SessionLocal()
    try:
        created, total = seed_release_gates(db, registry_path=REGISTRY_PATH)
        print(f"Release gates: {created} created, {total} registry keys discovered")
    finally:
        db.close()


if __name__ == "__main__":
    main()
