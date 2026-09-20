"""Find the real user + property list endpoints."""
from app.main import app

spec = app.openapi()
paths = spec.get("paths", {})

print("Paths containing 'user':")
for p in sorted(paths.keys()):
    if "user" in p.lower():
        print("   ", list(paths[p].keys()), p)

print()
print("Paths containing 'propert':")
for p in sorted(paths.keys()):
    if "propert" in p.lower() and "{" not in p:
        print("   ", list(paths[p].keys()), p)