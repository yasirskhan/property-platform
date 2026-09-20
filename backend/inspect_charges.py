"""See what a tenant's real charges look like."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
r = client.post(
    "/auth/login",
    json={"email": "admin@test.com", "password": "test1234"},
)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Which tenants exist?
r = client.get("/users", headers=headers)
users = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
tenants = [u for u in users if (u.get("role") or "").upper() == "TENANT"]
print("Tenants in org:")
for t in tenants:
    print("   ", t.get("id"), t.get("email"), t.get("role"))
print()

# Check the RentInvoice shape
from app.models.lease import RentInvoice
print("RentInvoice columns:")
for c in RentInvoice.__table__.columns:
    print("   ", c.name, c.type)

print()
print("RentInvoice rows (first 5):")
from app.core.database import SessionLocal
db = SessionLocal()
try:
    rows = db.query(RentInvoice).limit(5).all()
    if not rows:
        print("   (no rows)")
    for inv in rows:
        # Print every column
        for c in RentInvoice.__table__.columns:
            print(f"   {c.name} = {getattr(inv, c.name)}")
        print("   ---")
finally:
    db.close()