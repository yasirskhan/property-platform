"""Verify bills tables exist and AP account was seeded."""
import sqlite3
con = sqlite3.connect("property_platform.db")

print("Tables matching 'bill%':")
for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'bill%'"
).fetchall():
    print("  -", r[0])

print()
print("Alembic current version:")
for r in con.execute("SELECT version_num FROM alembic_version").fetchall():
    print("  -", r[0])

print()
print("GL account 2100 (Accounts Payable) per org:")
for r in con.execute(
    "SELECT organization_id, gl_number, name, account_type "
    "FROM gl_accounts WHERE gl_number='2100'"
).fetchall():
    print("  ", r)

con.close()