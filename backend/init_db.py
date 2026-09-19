# ============================================================
# init_db.py
# ------------------------------------------------------------
# This script creates the database tables.
#
# IMPORTANT: Every new model must be imported here, or
# SQLAlchemy won't know to create its table.
#
# To run:   python init_db.py
# ============================================================

from app.core.database import Base, engine

# ---- Import every model here ----
from app.models.user import User, Organization  # noqa: F401
from app.models.property import Property, Unit, PropertyAssignment  # noqa: F401
from app.models.lease import Lease, RentInvoice, Payment  # noqa: F401
from app.models.work_order import WorkOrder, WorkOrderUpdate  # noqa: F401
from app.models.password_reset import PasswordResetToken  # noqa: F401
from app.models.org_email import OrganizationEmailSettings  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.tax import PropertyTax, PropertyTaxPayment  # noqa: F401


def create_tables():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Done. Tables created (or already existed).")


if __name__ == "__main__":
    create_tables()