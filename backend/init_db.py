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
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun  # noqa: F401
from app.models.release_gate import ReleaseGate, ReleaseGateOrganization  # noqa: F401
from app.models.job_run import JobRun, JobDeadLetter  # noqa: F401
from app.models.data_retention_policy import DataRetentionPolicy  # noqa: F401
from app.models.billing import (  # noqa: F401
    Plan,
    Module,
    PlanModule,
    ModuleFeature,
    PricingTier,
    Subscription,
    SubscriptionItem,
    SubscriptionEvent,
    BillingSettings,
    PaymentMethod,
)
from app.models.subscription_billing import (  # noqa: F401
    SubscriptionInvoice,
    UsageRecord,
)
from app.models.billing_extras import AddOn, Discount  # noqa: F401
from app.models.billing_quotes import Quote, QuoteLineItem  # noqa: F401
from app.models.billing_checkout import BillingCheckoutSession  # noqa: F401
from app.models.fraud import FraudCase, FraudSignal  # noqa: F401
from app.models.organization_feature_setting import OrganizationFeatureSetting  # noqa: F401
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
from app.models.gl_account import GLAccount, GLAccountPostingRestriction  # noqa: F401
from app.models.gl_transaction import GLTransaction  # noqa: F401
from app.models.gl_entry import GLEntry  # noqa: F401
from app.models.recurring_journal_entry import (  # noqa: F401
    RecurringJournalEntry,
    RecurringJournalEntryLine,
)

# ---- Receipts (Phase 2 Step 5) ----
from app.models.receipt import Receipt  # noqa: F401
from app.models.receipt_line import ReceiptLine  # noqa: F401

# ---- Bills (Phase 2 Step 6) ----
from app.models.bill import Bill  # noqa: F401
from app.models.bill_line import BillLine  # noqa: F401
from app.models.bill_workflow import RecurringBill, RecurringBillLine, VendorCredit, VendorCreditLine  # noqa: F401
from app.models.check import Check, CheckBillAllocation  # noqa: F401

# ---- Deposits (Phase 2 Step 7) ----
from app.models.deposit import Deposit  # noqa: F401
from app.models.deposit_line import DepositLine  # noqa: F401

# ---- Management Fees (Phase 2 Step 9) ----
from app.models.management_fee_run import ManagementFeeRun  # noqa: F401
from app.models.owner_payout import OwnerPayout  # noqa: F401

# ---- Owner Statements (Phase 2 Step 10) ----
from app.models.owner_statement import OwnerPacketSettings, OwnerStatement  # noqa: F401

# ---- Bank Accounts (Phase 2 Step 4) ----
from app.models.bank_account import BankAccount  # noqa: F401
from app.models.trust_interest import TrustInterestReadiness  # noqa: F401
from app.models.bank_reconciliation import BankReconciliation, BankReconciliationItem, BankStatementLine  # noqa: F401
from app.models.bank_check_setup import BankCheckSetup  # noqa: F401
from app.models.bank_feed import BankFeedTransaction  # noqa: F401
from app.models.owner_ach import OwnerACHAccount  # noqa: F401
from app.models.accounting_key_account import AccountingKeyAccount  # noqa: F401
from app.models.accounting_settings import AccountingSettings  # noqa: F401

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
from app.models.user_personal_settings import UserPersonalSettings  # noqa: F401
from app.models.user_two_factor import UserTwoFactorSettings  # noqa: F401
from app.models.entity_note import EntityNote  # noqa: F401
from app.models.entity_attachment import EntityAttachment  # noqa: F401
from app.models.saved_report import SavedReport  # noqa: F401
from app.models.property_budget import PropertyBudgetLine  # noqa: F401
from app.models.property_group import PropertyGroup, PropertyGroupMembership  # noqa: F401
from app.models.affordable_program import AffordableProgram  # noqa: F401
from app.models.senior_housing import SeniorAgeRestriction, SeniorCareResource  # noqa: F401
from app.models.short_term_rental import ShortTermRentalChannel, ShortTermRentalNightlyPrice, ShortTermRentalTurnover  # noqa: F401
from app.models.hoa_association import HOAAssociation, HOAPropertyMembership, HOAContactLink  # noqa: F401
from app.models.hoa_assessment import HOAAssessmentProposal  # noqa: F401
from app.models.hoa_member_assessment import HOAAssessmentDecision, HOAMemberAssessmentCharge  # noqa: F401
from app.models.hoa_member_assessment_payment import HOAMemberAssessmentPayment  # noqa: F401
from app.models.hoa_annual_budget import HOAAnnualBudget  # noqa: F401
from app.models.hoa_annual_assessment_increase import HOAAnnualAssessmentIncrease  # noqa: F401
from app.models.hoa_observation import HOAObservation  # noqa: F401
from app.models.hoa_meeting_draft import HOAMeetingDraft  # noqa: F401
from app.models.hoa_meeting_workspace import HOAMeetingParticipation, HOAMotionDraft  # noqa: F401
from app.models.hoa_arc_intake import HOAARCIntake  # noqa: F401
from app.models.hoa_arc_application import HOAARCApplication, HOAARCApplicationAttachment, HOAARCReviewEvent  # noqa: F401
from app.models.hoa_arc_decision import HOAARCDecision, HOAARCMemberCharge, HOAARCFollowUp, HOAARCNotification  # noqa: F401
from app.models.hoa_governing_evidence import HOAGoverningEvidence  # noqa: F401
from app.models.hoa_document_delivery import HOADocumentDelivery  # noqa: F401
from app.models.hoa_procedure_policy import HOAProcedurePolicy  # noqa: F401
from app.models.hoa_violation_case import HOAViolationCase  # noqa: F401
from app.models.hoa_violation_case_event import HOAViolationCaseEvent  # noqa: F401
from app.models.hoa_violation_recipient import HOAViolationRecipientDraft  # noqa: F401
from app.models.hoa_violation_correspondence import HOAViolationCorrespondenceDraft  # noqa: F401
from app.models.hoa_violation_notice_delivery import HOAViolationNoticeDelivery  # noqa: F401
from app.models.hoa_violation_service_record import HOAViolationServiceRecord  # noqa: F401
from app.models.hoa_violation_hearing_record import HOAViolationHearingRecord  # noqa: F401
from app.models.hoa_violation_fine import HOAViolationFine  # noqa: F401
from app.models.hoa_violation_fine_payment import HOAViolationFinePayment  # noqa: F401
from app.models.hoa_violation_fine_appeal import HOAFineAppeal  # noqa: F401
from app.models.hoa_fine_appeal_notification import HOAFineAppealNotification  # noqa: F401
from app.models.hoa_violation_evidence import HOAViolationEvidence  # noqa: F401
from app.models.hoa_case_task import HOACaseTask  # noqa: F401
from app.models.hoa_reserve_account import HOAReserveAccount  # noqa: F401
from app.models.hoa_reserve_movement_draft import HOAReserveMovementDraft  # noqa: F401
from app.models.hoa_reserve_movement_decision import HOAReserveMovementDecision  # noqa: F401
from app.models.hoa_board import HOABoardSeat, HOABoardRuleDraft  # noqa: F401
from app.models.hoa_ballot import HOABallotRecord  # noqa: F401
from app.models.hoa_board_vote import HOABoardVote  # noqa: F401
from app.models.hoa_board_rule_adoption import HOABoardRuleAdoption  # noqa: F401
from app.models.hoa_board_motion_outcome import HOABoardMotionOutcome  # noqa: F401
from app.models.hoa_meeting_minutes import HOAMeetingMinutesDraft, HOAMeetingMinutesApproval  # noqa: F401
from app.models.hoa_payer_draft import HOAPayerDraft  # noqa: F401
from app.models.hoa_planned_occurrence import HOAPlannedOccurrence  # noqa: F401
from app.models.commercial_lease_abstract import CommercialLeaseAbstract  # noqa: F401
from app.models.commercial_operating_charge import CommercialOperatingCharge  # noqa: F401
from app.models.commercial_cam_reconciliation import CommercialCAMReconciliation  # noqa: F401
from app.models.commercial_percentage_rent import CommercialPercentageRentCharge  # noqa: F401
from app.models.commercial_ti_allowance import CommercialTIAllowanceUse  # noqa: F401
from app.models.affordable_interest import AffordableInterest  # noqa: F401
from app.models.affordable_evidence import AffordableEvidence  # noqa: F401
from app.models.affordable_building import AffordableBuilding  # noqa: F401
from app.models.affordable_8609_readiness import Affordable8609Readiness  # noqa: F401
from app.models.affordable_8609_document import Affordable8609Document  # noqa: F401
from app.models.affordable_8609_annual import Affordable8609Annual  # noqa: F401
from app.models.unit_inspection import UnitInspectionRecord  # noqa: F401
from app.models.vendor import Vendor  # noqa: F401
from app.models.contact import Contact  # noqa: F401
from app.models.application_private_details import ApplicationPrivateDetails  # noqa: F401
from app.models.application_fee_attempt import ApplicationFeeAttempt  # noqa: F401
from app.models.tag import Tag, EntityTag  # noqa: F401
from app.models.vendor_insurance import VendorInsurance  # noqa: F401
from app.models.letter_template import LetterTemplate  # noqa: F401
from app.models.lease_template import LeaseTemplate, LeaseTemplateAddendum  # noqa: F401
from app.models.prospect import Prospect  # noqa: F401
from app.models.guest_card import GuestCard  # noqa: F401
from app.models.tax_profile import TaxProfile  # noqa: F401
from app.models.tax_w9_document import TaxW9Document  # noqa: F401
from app.models.tax_1099_review import Tax1099Review  # noqa: F401
from app.models.currency import Currency  # noqa: F401
from app.models.charge import Charge  # noqa: F401


def create_tables():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Done. Tables created (or already existed).")


if __name__ == "__main__":
    create_tables()
