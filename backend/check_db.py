import sqlite3

conn = sqlite3.connect("property_platform.db")
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
conn.close()

print("Tables in database:", tables)