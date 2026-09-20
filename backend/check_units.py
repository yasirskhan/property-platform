import sqlite3
c = sqlite3.connect("property_platform.db")

print("=== SCHEMA: units ===")
row = c.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='units'"
).fetchone()
print(row[0] if row else "(not found)")

print()
print("=== SCHEMA: properties (id + organization_id check) ===")
for r in c.execute("PRAGMA table_info(properties)").fetchall():
    if r[1] in ("id", "organization_id"):
        print(r)

print()
print("=== SCHEMA: users (id + organization_id check) ===")
for r in c.execute("PRAGMA table_info(users)").fetchall():
    if r[1] in ("id", "organization_id"):
        print(r)

print()
print("=== ALEMBIC HEAD ===")
print(c.execute("SELECT version_num FROM alembic_version").fetchone())

c.close()