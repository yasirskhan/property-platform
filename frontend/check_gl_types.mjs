// Fetch GL accounts and print distinct account_type values.
const r = await fetch("http://127.0.0.1:8000/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: "admin@test.com", password: "test1234" }),
});
const { access_token } = await r.json();
const a = await fetch("http://127.0.0.1:8000/api/accounting/gl-accounts", {
  headers: { Authorization: `Bearer ${access_token}` },
});
const data = await a.json();
const types = new Set();
for (const g of data.groups) types.add(g.account_type);
console.log("account_type values seen:", [...types]);
console.log("First few INCOME accounts:");
for (const g of data.groups) {
  if (g.account_type && g.account_type.toUpperCase().includes("INCOME")) {
    for (const acc of g.accounts.slice(0, 3)) {
      console.log("  ", acc.gl_number, acc.name);
    }
  }
}