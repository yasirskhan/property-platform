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
from app.models.platform_user import PlatformUser  # noqa: F401
from app.models.release_gate import ReleaseGate, ReleaseGateOrganization  # noqa: F401
from app.models.job_run import JobRun, JobDeadLetter  # noqa: F401
from app.models.property import Property, Unit, PropertyAssignment  # noqa: F401
from app.models.lease import Lease, RentInvoice, Payment  # noqa: F401
from app.models.work_order import WorkOrder, WorkOrderUpdate  # noqa: F401
from app.models.password_reset import PasswordResetToken  # noqa: F401
from app.models.org_email import OrganizationEmailSettings  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.tax import PropertyTax, PropertyTaxPayment  # noqa: F401
from app.models.utility import (  # noqa: F401
    PropertyUtility,
    UtilityBill,
    TrashPickupSchedule,
)
from app.models.insurance import PropertyInsurance  # noqa: F401
from app.models.expense import PropertyExpense  # noqa: F401
from app.models.tenant_insurance import TenantInsurance  # noqa: F401
from app.models.platform_settings import PlatformSetting  # noqa: F401
from app.models.income import PropertyIncome  # noqa: F401
from app.models.application import LeaseApplication, ApplicationPayment  # noqa: F401
from app.models.screening import ScreeningProvider, OrganizationScreeningSettings  # noqa: F401

# ---- General Ledger (Phase 2 Steps 1 + 2) ----
from app.models.gl_account import GLAccount  # noqa: F401
from app.models.gl_transaction import GLTransaction  # noqa: F401
from app.models.gl_entry import GLEntry  # noqa: F401

# ---- Receipts (Phase 2 Step 5) ----
from app.models.receipt import Receipt  # noqa: F401
from app.models.receipt_line import ReceiptLine  # noqa: F401

# ---- Bills (Phase 2 Step 6) ----
from app.models.bill import Bill  # noqa: F401
from app.models.bill_line import BillLine  # noqa: F401

# ---- Deposits (Phase 2 Step 7) ----
from app.models.deposit import Deposit  # noqa: F401
from app.models.deposit_line import DepositLine  # noqa: F401

# ---- Management Fees (Phase 2 Step 9) ----
from app.models.management_fee_run import ManagementFeeRun  # noqa: F401

# ---- Owner Statements (Phase 2 Step 10) ----
from app.models.owner_statement import OwnerStatement  # noqa: F401

# ---- Bank Accounts (Phase 2 Step 4) ----
from app.models.bank_account import BankAccount  # noqa: F401

# ---- Property Detail tabs (Phase 3) ----
from app.models.property_amenity import PropertyAmenity  # noqa: F401
from app.models.property_appliance import PropertyAppliance  # noqa: F401
from app.models.property_improvement import PropertyImprovement  # noqa: F401
from app.models.property_photo import PropertyPhoto  # noqa: F401

# ---- Settings / permissions / Phase 3.5+ ----
from app.models.sidebar_preference import SidebarPreference  # noqa: F401
from app.models.menu_permission import MenuPermission  # noqa: F401
from app.models.user_permission import UserPermission  # noqa: F401
from app.models.user_display_preference import UserDisplayPreference  # noqa: F401
from app.models.currency import Currency  # noqa: F401
from app.models.charge import Charge  # noqa: F401


def create_tables():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Done. Tables created (or already existed).")


if __name__ == "__main__":
    create_tables()