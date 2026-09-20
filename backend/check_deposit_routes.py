"""Check deposits routes are in the OpenAPI spec."""
from app.main import app

spec = app.openapi()
paths = spec.get("paths", {})

print(f"Total paths: {len(paths)}")
print()
print("Deposit paths:")
for p in sorted(paths.keys()):
    if "deposit" in p.lower():
        methods = list(paths[p].keys())
        print(f"   {methods} {p}")