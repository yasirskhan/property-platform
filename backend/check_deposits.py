"""Verify deposits tables, new receipt columns, and menu seed."""
import sqlite3
con = sqlite3.connect("property_platform.db")

print("Tables matching 'deposit%':")
for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'deposit%'"
).fetchall():
    print("  -", r[0])

print()
print("Alembic version:")
for r in con.execute("SELECT version_num FROM alembic_version").fetchall():
    print("  -", r[0])

print()
print("New receipts columns:")
cols = [row[1] for row in con.execute("PRAGMA table_info(receipts)").fetchall()]
for name in cols:
    if name in ("is_deposited", "deposit_id"):
        print("  -", name, "present")

print()
print("Menu seed count (ACCOUNTING.DEPOSITS):")
count = con.execute(
    "SELECT COUNT(*) FROM menu_permissions WHERE menu_key='ACCOUNTING.DEPOSITS'"
).fetchone()[0]
print("  ", count, "rows")

con.close()