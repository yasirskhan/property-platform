"""
q.py — Quick query helper.

Run any SQL against the project's SQLite database without
wrestling with PowerShell quote mangling.

Usage (from the backend folder, venv active):

    python q.py "SELECT * FROM properties"
    python q.py "SELECT COUNT(*) FROM users"
    python q.py "SELECT name FROM sqlite_master WHERE type='table'"
    python q.py "PRAGMA table_info(receipts)"

Read-only by default — but anything goes. Be careful with
DELETE / DROP / UPDATE / INSERT.
"""
import sqlite3
import sys

DB = "property_platform.db"

sql = " ".join(sys.argv[1:]).strip()
if not sql:
    print("Usage: python q.py \"<SQL>\"")
    print()
    print("Examples:")
    print("  python q.py \"SELECT COUNT(*) FROM receipts\"")
    print("  python q.py \"PRAGMA table_info(property_appliances)\"")
    sys.exit(1)

con = sqlite3.connect(DB)
try:
    cursor = con.execute(sql)
    rows = cursor.fetchall()

    if not rows:
        print("(no rows)")
    else:
        # Column headers if available
        if cursor.description:
            headers = [d[0] for d in cursor.description]
            print(" | ".join(headers))
            print("-" * 60)
        for row in rows:
            print(row)
finally:
    con.close()