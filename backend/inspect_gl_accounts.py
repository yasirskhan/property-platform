"""Dump the raw GL-accounts response so we know its shape."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

r = client.post(
    "/auth/login",
    json={"email": "admin@test.com", "password": "test1234"},
)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Try the endpoint we used
r = client.get("/api/accounting/gl-accounts", headers=headers)
print("GET /api/accounting/gl-accounts ->", r.status_code)
print("Raw body (first 1500 chars):")
print(r.text[:1500])
print()

# Try to see the actual registered GL endpoints
print("OpenAPI paths containing 'gl-account':")
spec = app.openapi()
for p in sorted(spec.get("paths", {}).keys()):
    if "gl-account" in p.lower():
        print("   ", p)