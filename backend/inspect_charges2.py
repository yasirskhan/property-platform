"""Why does /open-charges return 0 rows for tenant1?"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
r = client.post("/auth/login", json={"email": "admin@test.com", "password": "test1234"})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Get tenant list
r = client.get("/users", headers=headers)
users = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
tenants = [u for u in users if (u.get("role") or "").upper() == "TENANT"]
print("Tenants:", [(t["id"], t.get("email")) for t in tenants])
print()

# Call the endpoint for each tenant
for t in tenants:
    r = client.get(
        f"/api/accounting/receipts/tenant/{t['id']}/open-charges",
        headers=headers,
    )
    print(f"Tenant {t['id']} ({t.get('email')}): status {r.status_code}")
    body = r.json()
    print("   lease_id:", body.get("lease_id"))
    print("   rent_gl_account_id:", body.get("rent_gl_account_id"))
    print("   items:", body.get("total"), "row(s)")
    for it in body.get("items", [])[:3]:
        print("      ", it)
    print()

# Show leases directly
from app.core.database import SessionLocal
from app.models.lease import Lease, RentInvoice

db = SessionLocal()
try:
    print("Leases in DB:")
    for l in db.query(Lease).all():
        print(
            f"   id={l.id} org={l.organization_id} "
            f"tenant_user_id={getattr(l, 'tenant_user_id', 'MISSING')} "
            f"property_id={getattr(l, 'property_id', 'MISSING')}"
        )
finally:
    db.close()