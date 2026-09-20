"""What columns does Lease actually have?"""
from app.models.lease import Lease, RentInvoice

print("Lease columns:")
for c in Lease.__table__.columns:
    print("   ", c.name, c.type)

print()
print("RentInvoice columns:")
for c in RentInvoice.__table__.columns:
    print("   ", c.name, c.type)

print()
print("All leases in DB:")
from app.core.database import SessionLocal
db = SessionLocal()
try:
    for l in db.query(Lease).all():
        row = {c.name: getattr(l, c.name) for c in Lease.__table__.columns}
        print("   ", row)
finally:
    db.close()