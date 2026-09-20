"""Does the API return ACCOUNTING.DEPOSITS in the menu?"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
r = client.post(
    "/auth/login",
    json={"email": "admin@test.com", "password": "test1234"},
)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

r = client.get("/api/menu/me", headers=headers)
print("Menu status:", r.status_code)
print()
print("Raw response (first 1500 chars):")
print(r.text[:1500])