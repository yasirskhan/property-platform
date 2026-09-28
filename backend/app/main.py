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
from app.routers import rental_applications as rental_applications_router
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
from app.routers import checks as checks_router
from app.routers import bank_reconciliation as bank_reconciliation_router
from app.routers import bank_adjustments as bank_adjustments_router
from app.routers import bank_feed as bank_feed_router
from app.routers import check_setup as check_setup_router
from app.routers import ach_files as ach_files_router
from app.routers import owner_ach as owner_ach_router
from app.routers import owner_held_deposits as owner_held_deposits_router
from app.routers import owner_payouts as owner_payouts_router
from app.routers import accounting_settings as accounting_settings_router
from app.routers import my_settings as my_settings_router
from app.routers import audit_center as audit_center_router
from app.routers import two_factor as two_factor_router
from app.routers import entity_notes as entity_notes_router
from app.routers import entity_attachments as entity_attachments_router
from app.routers import reporting as reporting_router
from app.routers import vendors as vendors_router
from app.routers import contacts as contacts_router
from app.routers import tags as tags_router
from app.routers import vendor_insurance as vendor_insurance_router
from app.routers import property_budgets as property_budgets_router
from app.routers import property_groups as property_groups_router
from app.routers import unit_inspections as unit_inspections_router
from app.routers import letters as letters_router
from app.routers import lease_templates as lease_templates_router
from app.routers import prospects as prospects_router
from app.routers import guest_cards as guest_cards_router
from app.routers import rubs_readiness as rubs_readiness_router
from app.routers import affordable_programs as affordable_programs_router
from app.routers import hoa_associations as hoa_associations_router
from app.routers import hoa_assessments as hoa_assessments_router
from app.routers import hoa_observations as hoa_observations_router
from app.routers import hoa_meeting_drafts as hoa_meeting_drafts_router
from app.routers import hoa_meeting_workspace as hoa_meeting_workspace_router
from app.routers import hoa_arc_intake as hoa_arc_intake_router
from app.routers import hoa_arc_applications as hoa_arc_applications_router
from app.routers import hoa_governing_evidence as hoa_governing_evidence_router
from app.routers import hoa_procedure_policies as hoa_procedure_policies_router
from app.routers import hoa_violation_cases as hoa_violation_cases_router
from app.routers import hoa_reserve_accounts as hoa_reserve_accounts_router
from app.routers import hoa_board as hoa_board_router
from app.routers import hoa_ballots as hoa_ballots_router
from app.routers import hoa_meeting_minutes as hoa_meeting_minutes_router
from app.routers import hoa_payer_drafts as hoa_payer_drafts_router
from app.routers import commercial_lease_abstracts as commercial_lease_abstracts_router
from app.routers import affordable_interest as affordable_interest_router
from app.routers import affordable_evidence as affordable_evidence_router
from app.routers import affordable_buildings as affordable_buildings_router
from app.routers import affordable_8609_readiness as affordable_8609_readiness_router
from app.routers import affordable_8609_documents as affordable_8609_documents_router
from app.routers import affordable_8609_annual as affordable_8609_annual_router
from app.routers import trust_interest as trust_interest_router
from app.routers import positive_pay as positive_pay_router
from app.routers import owner_packets as owner_packets_router
from app.routers import tax_profiles as tax_profiles_router
from app.routers import tax_w9 as tax_w9_router
from app.routers import tax_1099_reviews as tax_1099_reviews_router

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
app.include_router(rental_applications_router.router)
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
app.include_router(checks_router.router)
app.include_router(bank_reconciliation_router.router)
app.include_router(bank_adjustments_router.router)
app.include_router(bank_feed_router.router)
app.include_router(check_setup_router.router)
app.include_router(ach_files_router.router)
app.include_router(owner_ach_router.router)
app.include_router(owner_held_deposits_router.router)
app.include_router(owner_payouts_router.router)
app.include_router(accounting_settings_router.router)
app.include_router(my_settings_router.router)
app.include_router(audit_center_router.router)
app.include_router(two_factor_router.router)
app.include_router(entity_notes_router.router)
app.include_router(entity_attachments_router.router)
app.include_router(reporting_router.router)
app.include_router(vendors_router.router)
app.include_router(contacts_router.router)
app.include_router(tags_router.router)
app.include_router(vendor_insurance_router.router)
app.include_router(property_budgets_router.router)
app.include_router(property_groups_router.router)
app.include_router(unit_inspections_router.router)
app.include_router(letters_router.router)
app.include_router(lease_templates_router.router)
app.include_router(prospects_router.router)
app.include_router(guest_cards_router.router)
app.include_router(rubs_readiness_router.router)
app.include_router(affordable_programs_router.router)
app.include_router(hoa_associations_router.router)
app.include_router(hoa_assessments_router.router)
app.include_router(hoa_observations_router.router)
app.include_router(hoa_meeting_drafts_router.router)
app.include_router(hoa_meeting_workspace_router.router)
app.include_router(hoa_arc_intake_router.router)
app.include_router(hoa_arc_applications_router.router)
app.include_router(hoa_governing_evidence_router.router)
app.include_router(hoa_procedure_policies_router.router)
app.include_router(hoa_violation_cases_router.router)
app.include_router(hoa_reserve_accounts_router.router)
app.include_router(hoa_board_router.router)
app.include_router(hoa_ballots_router.router)
app.include_router(hoa_meeting_minutes_router.router)
app.include_router(hoa_payer_drafts_router.router)
app.include_router(commercial_lease_abstracts_router.router)
app.include_router(affordable_interest_router.router)
app.include_router(affordable_evidence_router.router)
app.include_router(affordable_buildings_router.router)
app.include_router(affordable_8609_readiness_router.router)
app.include_router(affordable_8609_documents_router.router)
app.include_router(affordable_8609_annual_router.router)
app.include_router(trust_interest_router.router)
app.include_router(positive_pay_router.router)
app.include_router(owner_packets_router.router)
app.include_router(tax_profiles_router.router)
app.include_router(tax_w9_router.router)
app.include_router(tax_1099_reviews_router.router)


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