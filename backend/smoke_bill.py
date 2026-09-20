"""Smoke test: enter a bill, pay it, verify the GL both times."""
from datetime import date

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# 1. Log in
r = client.post(
    "/auth/login",
    json={"email": "admin@test.com", "password": "test1234"},
)
print("Login status:", r.status_code)
if r.status_code != 200:
    print(r.text)
    raise SystemExit(1)

token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. Get GL accounts
r = client.get("/api/accounting/gl-accounts", headers=headers)
data = r.json()
accounts = []
for grp in data.get("groups", []):
    accounts.extend(grp.get("accounts", []))

cash = next((a for a in accounts if a.get("gl_number") == "1150"), None)
plumbing = next((a for a in accounts if a.get("gl_number") == "6852"), None)
ap = next((a for a in accounts if a.get("gl_number") == "2100"), None)

if not (cash and plumbing and ap):
    print("Missing one of: 1150, 6852, 2100")
    print("Seen:", [a.get("gl_number") for a in accounts])
    raise SystemExit(1)

print("Cash:    ", cash["gl_number"], cash["name"])
print("Expense: ", plumbing["gl_number"], plumbing["name"])
print("Payable: ", ap["gl_number"], ap["name"])
print()

# 3. Enter bill (DR 6852 / CR 2100)
payload = {
    "payee_name": "Joe Plumber",
    "bill_date": str(date.today()),
    "due_date": str(date.today()),
    "reference_number": "INV-1001",
    "remarks": "Kitchen sink repair",
    "lines": [
        {
            "gl_account_id": plumbing["id"],
            "description": "Fix kitchen sink",
            "amount": "250.00",
        }
    ],
}
r = client.post("/api/accounting/bills", json=payload, headers=headers)
print("Enter bill status:", r.status_code)
if r.status_code != 201:
    print(r.text)
    raise SystemExit(1)

bill = r.json()
print("Bill id:", bill["id"])
print("Bill number:", bill["bill_number"])
print("Amount:", bill["amount"])
print("Status:", bill["status"])
print("GL txn id:", bill["gl_transaction_id"])
print()

# 4. Check the GL for the bill entry
txn_id = bill["gl_transaction_id"]
r = client.get(f"/api/accounting/gl-transactions/{txn_id}", headers=headers)
txn = r.json()
print("Bill GL transaction:")
print("  type:", txn["transaction_type"])
print("  memo:", txn["memo"])
for e in txn["entries"]:
    print(
        f"   {e['gl_account_number']} {e['gl_account_name']}: "
        f"DR {e['debit']} CR {e['credit']}"
    )
print()

# 5. Pay the bill (DR 2100 / CR 1150)
pay_payload = {
    "payment_date": str(date.today()),
    "cash_gl_account_id": cash["id"],
    "amount": "250.00",
    "reference_number": "CHK-5001",
    "remarks": "Paid Joe Plumber",
}
r = client.post(
    f"/api/accounting/bills/{bill['id']}/pay",
    json=pay_payload,
    headers=headers,
)
print("Pay bill status:", r.status_code)
if r.status_code != 201:
    print(r.text)
    raise SystemExit(1)

paid = r.json()
print("Bill status after pay:", paid["status"])
print("Amount paid:", paid["amount_paid"])
print()

# 6. Find the payment GL transaction (latest BILL txn for this bill)
r = client.get(
    "/api/accounting/gl-transactions",
    headers=headers,
    params={"source_type": "bill_payment", "source_id": bill["id"]},
)
txn_list = r.json()
print(f"Found {txn_list['total']} payment transaction(s).")
if txn_list["items"]:
    payment_txn_id = txn_list["items"][0]["id"]
    r = client.get(
        f"/api/accounting/gl-transactions/{payment_txn_id}", headers=headers
    )
    txn2 = r.json()
    print("Payment GL transaction:")
    for e in txn2["entries"]:
        print(
            f"   {e['gl_account_number']} {e['gl_account_name']}: "
            f"DR {e['debit']} CR {e['credit']}"
        )

print()
print("SUCCESS")