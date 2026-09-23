"""Prove a SQLite backup can be created and restored without altering the source DB.

Current local-development proof only. Production PostgreSQL backup/restore verification
belongs in staging once that environment exists.
"""
from __future__ import annotations

import argparse
import sqlite3
import tempfile
from pathlib import Path


def _snapshot(conn: sqlite3.Connection) -> tuple[list[str], dict[str, int]]:
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"SQLite integrity_check failed: {integrity}")

    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    ]
    counts: dict[str, int] = {}
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
    return tables, counts


def verify_backup_restore(source: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)

    source = source.resolve()
    with tempfile.TemporaryDirectory(prefix="property-platform-backup-test-") as tmp:
        backup_path = Path(tmp) / "backup.db"
        restore_path = Path(tmp) / "restored.db"

        with sqlite3.connect(source) as src, sqlite3.connect(backup_path) as dst:
            before = _snapshot(src)
            src.backup(dst)
            backup_snapshot = _snapshot(dst)

        with sqlite3.connect(backup_path) as src, sqlite3.connect(restore_path) as dst:
            src.backup(dst)

        with sqlite3.connect(restore_path) as restored:
            after = _snapshot(restored)

        if before != backup_snapshot or before != after:
            raise RuntimeError("Backup/restore verification mismatch in table list or row counts")

        print(
            f"Backup/restore VERIFIED for {source.name}: "
            f"{len(before[0])} tables, row counts preserved, integrity_check=ok."
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "database",
        nargs="?",
        default="property_platform.db",
        help="SQLite database path (default: property_platform.db)",
    )
    args = parser.parse_args()
    verify_backup_restore(Path(args.database))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
