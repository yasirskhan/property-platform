from __future__ import annotations

import sqlite3
from pathlib import Path

from backup_restore_check import verify_backup_restore


def test_sqlite_backup_restore_preserves_schema_and_rows(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    conn = sqlite3.connect(source)
    conn.executescript(
        """
        CREATE TABLE example (id INTEGER PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO example(value) VALUES ('one'), ('two'), ('three');
        CREATE TABLE empty_table (id INTEGER PRIMARY KEY);
        """
    )
    conn.commit()
    conn.close()

    verify_backup_restore(source)
