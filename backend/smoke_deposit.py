"""Smoke test: create a deposit from undeposited receipts."""
from datetime import date

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# 1. Log in
r = client.post(
    "/auth/login",
    json={"email": "admin@test.com", "password": "test1234"},
)
print("Login:", r.status_code)
if r.status_code != 200:
    print(r.text)
    raise SystemExit(1)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. List undeposited receipts
r = client.get(
    "/api/accounting/deposits/undeposited-receipts", headers=headers
)
print("Undeposited list:", r.status_code)
data = r.json()
print(f"  Count: {data['total']}")
print(f"  Total amount: {data['total_amount']}")
for it in data["items"]:
    print(
        f"    #{it['id']}  {it['receipt_date']}  {it['type']}  "
        f"${it['amount']}  ({it.get('payer_label')})  "
        f"acct {it.get('cash_gl_account_number')}"
    )
print()

if data["total"] == 0:
    print("Nothing to deposit. Exiting.")
    raise SystemExit(0)

# 3. Pick the first two (or just one if only one)
receipt_ids = [it["id"] for it in data["items"][:2]]
cash_gl_account_id = data["items"][0]["cash_gl_account_id"]
print("Depositing receipts:", receipt_ids)
print("Bank account id:", cash_gl_account_id)
print()

# 4. Create the deposit
payload = {
    "bank_gl_account_id": cash_gl_account_id,
    "deposit_date": str(date.today()),
    "deposit_number": "TEST-001",
    "description": "Smoke test deposit",
    "receipt_ids": receipt_ids,
}
r = client.post(
    "/api/accounting/deposits", json=payload, headers=headers
)
print("Create deposit:", r.status_code)
if r.status_code != 201:
    print(r.text)
    raise SystemExit(1)

dep = r.json()
print("  id:", dep["id"])
print("  number:", dep["deposit_number"])
print("  date:", dep["deposit_date"])
print("  total:", dep["total"])
print("  bank:", dep["bank_gl_account_number"], dep["bank_gl_account_name"])
print("  line_count:", dep["line_count"])
for ln in dep["lines"]:
    print(
        f"    receipt #{ln['receipt_id']}  {ln['receipt_date']}  "
        f"${ln['receipt_amount']}  ({ln['receipt_payer']})"
    )
print()

# 5. Re-list undeposited to confirm they're gone
r = client.get(
    "/api/accounting/deposits/undeposited-receipts", headers=headers
)
data2 = r.json()
print(f"Undeposited after: {data2['total']} receipts remain")
print()

# 6. Try to deposit the same receipts again — should be rejected
r = client.post(
    "/api/accounting/deposits", json=payload, headers=headers
)
print("Duplicate attempt status:", r.status_code)
if r.status_code == 400:
    print("  (correctly rejected):", r.json().get("detail"))
print()

# 7. Fetch the deposit detail
r = client.get(
    f"/api/accounting/deposits/{dep['id']}", headers=headers
)
print("Get deposit detail:", r.status_code)
d2 = r.json()
print("  number:", d2["deposit_number"])
print("  total:", d2["total"])
print()

print("SUCCESS")