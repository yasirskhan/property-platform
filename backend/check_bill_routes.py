"""Check bills routes are registered in OpenAPI spec."""
from app.main import app

spec = app.openapi()
paths = spec.get("paths", {})

print(f"Total documented paths: {len(paths)}")
print()
print("Bill paths in OpenAPI spec:")
for p in sorted(paths.keys()):
    if "bill" in p.lower() and "receipt" not in p.lower():
        methods = list(paths[p].keys())
        print(f"   {methods} {p}")