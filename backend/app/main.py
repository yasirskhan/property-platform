# ============================================================
# main.py
# ------------------------------------------------------------
# The entry point of the backend.
#
# Run with:   uvicorn app.main:app --reload
#
# Then open:
#   http://127.0.0.1:8000          -> basic welcome
#   http://127.0.0.1:8000/docs     -> interactive API docs
#   http://127.0.0.1:8000/health   -> health check
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.observability import init_sentry
from app.routers import auth as auth_router
from app.routers import properties as properties_router
from app.routers import users as users_router
from app.routers import leases as leases_router
from app.routers import payments as payments_router
from app.routers import work_orders as work_orders_router
from app.routers import password_reset as password_reset_router
from app.routers import org_email as org_email_router
from app.routers import uploads as uploads_router
from app.routers import taxes as taxes_router
from app.routers import utilities as utilities_router
from app.routers import insurance as insurance_router
from app.routers import expenses as expenses_router
from app.routers import tenant_insurance as tenant_insurance_router
from app.routers import platform_settings as platform_settings_router
from app.routers import screening_settings as screening_settings_router
from app.routers import sidebar_preference as sidebar_preference_router
from app.routers import menu_permissions as menu_permissions_router
from app.routers import organizations as organizations_router
from app.routers import gl_accounts as gl_accounts_router
from app.routers import gl_transactions as gl_transactions_router
from app.routers import gl_reports as gl_reports_router
from app.routers import receipts as receipts_router
from app.routers import bills as bills_router
from app.routers import deposits as deposits_router
from app.routers import diagnostics as diagnostics_router
from app.routers import management_fees as management_fees_router
from app.routers import owner_statements as owner_statements_router
from app.routers import bank_accounts as bank_accounts_router
from app.routers import journal_entries as journal_entries_router
from app.routers import property_amenities as property_amenities_router
from app.routers import property_appliances as property_appliances_router
from app.routers import property_improvements as property_improvements_router
from app.routers import property_photos as property_photos_router
from app.models.user_display_preference import UserDisplayPreference  # noqa: F401
from app.models.charge import Charge  # noqa: F401
from app.routers import settings_display as settings_display_router
from app.routers import currencies as currencies_router
from app.routers import charges as charges_router
from app.routers import platform_auth as platform_auth_router
from app.routers import platform_flags as platform_flags_router
from app.routers import platform_jobs as platform_jobs_router
from app.routers import platform_fraud as platform_fraud_router
from app.routers import platform_admin as platform_admin_router
from app.routers import observability as observability_router
from app.routers import billing_checkout as billing_checkout_router
from app.routers import features as features_router

# ------------------------------------------------------------
# Create the FastAPI app
# ------------------------------------------------------------
init_sentry()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Property Management Platform API",
)


# ------------------------------------------------------------
# CORS
# ------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# Register routers
# ------------------------------------------------------------
app.include_router(auth_router.router)
app.include_router(properties_router.router)
app.include_router(users_router.router)
app.include_router(leases_router.router)
app.include_router(payments_router.router)
app.include_router(work_orders_router.router)
app.include_router(password_reset_router.router)
app.include_router(org_email_router.router)
app.include_router(uploads_router.router)
app.include_router(taxes_router.router)
app.include_router(utilities_router.router)
app.include_router(insurance_router.router)
app.include_router(expenses_router.router)
app.include_router(tenant_insurance_router.router)
app.include_router(platform_settings_router.router)
app.include_router(screening_settings_router.router)
app.include_router(sidebar_preference_router.router)
app.include_router(menu_permissions_router.router)
app.include_router(organizations_router.router)
app.include_router(gl_accounts_router.router)
app.include_router(gl_transactions_router.router)
app.include_router(gl_reports_router.router)
app.include_router(receipts_router.router)
app.include_router(bills_router.router)
app.include_router(deposits_router.router)
app.include_router(diagnostics_router.router)
app.include_router(management_fees_router.router)
app.include_router(owner_statements_router.router)
app.include_router(bank_accounts_router.router)
app.include_router(journal_entries_router.router)
app.include_router(property_amenities_router.router)
app.include_router(property_appliances_router.router)
app.include_router(property_improvements_router.router)
app.include_router(property_photos_router.router)
app.include_router(settings_display_router.router)
app.include_router(currencies_router.router)
app.include_router(charges_router.router)
app.include_router(platform_auth_router.router)
app.include_router(platform_flags_router.router)
app.include_router(platform_jobs_router.router)
app.include_router(platform_fraud_router.router)
app.include_router(platform_admin_router.router)
app.include_router(observability_router.router)
app.include_router(billing_checkout_router.router)
app.include_router(features_router.router)


# ------------------------------------------------------------
# Root + health check
# ------------------------------------------------------------
@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "ok"}