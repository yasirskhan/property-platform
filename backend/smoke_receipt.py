"""Smoke test: create an OTHER receipt, then verify the GL."""
from datetime import date

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# 1. Log in as admin
r = client.post(
    "/auth/login",
    json={"email": "admin@test.com", "password": "test1234"},
)
print("Login status:", r.status_code)
if r.status_code != 200:
    print(r.text)
    raise SystemExit(1)

token = r.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

# 2. Grab GL accounts (grouped shape) and flatten
r = client.get("/api/accounting/gl-accounts", headers=headers)
print("GL accounts status:", r.status_code)
data = r.json()

accounts = []
for grp in data.get("groups", []):
    accounts.extend(grp.get("accounts", []))

cash_acct = next(
    (a for a in accounts if a.get("gl_number") == "1150"), None
)
income_acct = next(
    (a for a in accounts if a.get("gl_number") == "4450"), None
)

if not cash_acct or not income_acct:
    print("Could not find 1150 or 4450.")
    print("Numbers seen:", [a.get("gl_number") for a in accounts])
    raise SystemExit(1)

print("Cash account:", cash_acct["gl_number"], cash_acct["name"])
print("Income account:", income_acct["gl_number"], income_acct["name"])

# 3. Post an OTHER receipt for $1.00
payload = {
    "type": "OTHER",
    "receipt_date": str(date.today()),
    "amount": "1.00",
    "cash_gl_account_id": cash_acct["id"],
    "income_gl_account_id": income_acct["id"],
    "received_from": "Smoke Test",
    "exclude_from_mgmt_fee": True,
    "remarks": "Step 5 smoke test",
}
r = client.post(
    "/api/accounting/receipts", json=payload, headers=headers
)
print("Create receipt status:", r.status_code)
if r.status_code != 201:
    print(r.text)
    raise SystemExit(1)

receipt = r.json()
print("Receipt id:", receipt["id"])
print("GL transaction id:", receipt["gl_transaction_id"])
print("Lines:", len(receipt["lines"]))

# 4. Fetch the GL transaction and print it
txn_id = receipt["gl_transaction_id"]
r = client.get(
    f"/api/accounting/gl-transactions/{txn_id}", headers=headers
)
print()
print("GL transaction detail:")
txn = r.json()
print("  type:", txn["transaction_type"])
print("  date:", txn["transaction_date"])
print("  memo:", txn["memo"])
for e in txn["entries"]:
    print(
        f"   {e['gl_account_number']} {e['gl_account_name']}: "
        f"DR {e['debit']} CR {e['credit']}"
    )

print()
print("SUCCESS" if r.status_code == 200 else "FAIL")