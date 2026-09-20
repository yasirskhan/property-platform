"""See the shape of /api/users and /api/properties."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
r = client.post("/auth/login", json={"email": "admin@test.com", "password": "test1234"})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

r = client.get("/api/users", headers=headers)
print("GET /api/users ->", r.status_code)
print("Body[:600]:", r.text[:600])
print()

r = client.get("/api/properties", headers=headers)
print("GET /api/properties ->", r.status_code)
print("Body[:600]:", r.text[:600])