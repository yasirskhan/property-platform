"""Browser contract: HOA evidence remains a private, unverified staff reference.

This test uses a synthetic document in the disposable E2E database. It does
not supply, approve, or interpret any actual HOA governing instrument.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
import re

import pytest

import init_db  # noqa: F401 - register all SQLAlchemy models for live DB counts

playwright_sync = pytest.importorskip("playwright.sync_api")
expect = playwright_sync.expect
sync_playwright = playwright_sync.sync_playwright

from app.core.database import SessionLocal
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.gl_account import GLAccount
from app.models.contact import Contact
from app.models.entity_attachment import EntityAttachment
from app.models.hoa_association import HOAAssociation, HOAContactLink
from app.models.hoa_board import HOABoardSeat
from app.models.release_gate import ReleaseGate, ReleaseStage
from app.models.billing import Module, Plan, Subscription, SubscriptionItem, SubscriptionStatus
from app.models.user import User

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")
PROPERTY_ID = 900001
ASSOCIATION_NAME = "E2E Staff-Only Association"
DOCUMENT_NAME = "e2e-unverified-fixture.pdf"


@contextmanager
def _temporarily_release_hoa_ui():
    """Only the disposable E2E run may enable these otherwise hidden features."""
    if os.environ.get("E2E_SEED_ALLOWED", "").lower() != "true":
        raise RuntimeError("HOA browser test requires an explicitly disposable E2E database")
    db = SessionLocal()
    previous = {}
    subscription = None
    created_subscription = False
    created_item = None
    created_plan = None
    try:
        for key in ("release.properties.compliance", "release.properties.hoa", "release.documents.attachments"):
            gate = db.query(ReleaseGate).filter(ReleaseGate.key == key).one_or_none()
            if gate is None:
                gate = ReleaseGate(key=key, stage=ReleaseStage.ALL_ORGS)
                db.add(gate)
                db.flush()
                previous[key] = (gate.id, None)
            else:
                previous[key] = (gate.id, gate.stage)
                gate.stage = ReleaseStage.ALL_ORGS
        # Disposable E2E org only. Does not start billing or grant a real customer.
        actor = db.query(User).filter(User.email == EMAIL).one()
        module = db.query(Module).filter(Module.key == "hoa", Module.is_core.is_(False)).one()
        subscription = db.query(Subscription).filter(
            Subscription.organization_id == actor.organization_id,
        ).one_or_none()
        if subscription is None:
            created_plan = Plan(code="e2e-hoa-planning-entitlement", name="Synthetic HOA E2E Plan")
            db.add(created_plan)
            db.flush()
            subscription = Subscription(
                organization_id=actor.organization_id, plan_id=created_plan.id,
                status=SubscriptionStatus.ACTIVE,
            )
            db.add(subscription)
            db.flush()
            created_subscription = True
        elif subscription.status != SubscriptionStatus.ACTIVE:
            raise RuntimeError("Disposable HOA E2E subscription must be ACTIVE")
        previous_item = db.query(SubscriptionItem).filter(
            SubscriptionItem.subscription_id == subscription.id,
            SubscriptionItem.module_id == module.id,
        ).one_or_none()
        if previous_item is None:
            created_item = SubscriptionItem(
                subscription_id=subscription.id, module_id=module.id,
                unit_price_cents=7900,
            )
            db.add(created_item)
        db.commit()
        yield
    finally:
        db.rollback()
        if created_subscription and subscription is not None:
            db.delete(subscription)
            db.flush()
            if created_plan is not None:
                db.delete(created_plan)
        elif created_item is not None:
            db.delete(created_item)
        for identifier, prior_stage in previous.values():
            gate = db.get(ReleaseGate, identifier)
            if gate is not None:
                if prior_stage is None:
                    db.delete(gate)
                else:
                    gate.stage = prior_stage
        db.commit()
        db.close()


def _financial_counts() -> tuple[int, int]:
    db = SessionLocal()
    try:
        return db.query(Charge).count(), db.query(GLTransaction).count()
    finally:
        db.close()


def test_hoa_staff_evidence_upload_link_download_and_archive() -> None:
    with _temporarily_release_hoa_ui():
        before = _financial_counts()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(accept_downloads=True)
            try:
                page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
                page.locator('input[type="email"]').fill(EMAIL)
                page.locator('input[type="password"]').fill(PASSWORD)
                page.get_by_role("button", name="Log In").click()
                page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)

                page.goto(
                    f"{BASE_URL}/dashboard/properties/{PROPERTY_ID}",
                    wait_until="domcontentloaded",
                )
                expect(page.get_by_role("heading", name="E2E Test Property")).to_be_visible()
                page.get_by_role("button", name="Compliance", exact=True).click()
                expect(page.get_by_role("heading", name="HOA — recorded associations")).to_be_visible()

                page.get_by_label("Association name").fill(ASSOCIATION_NAME)
                page.get_by_role("button", name="Record association").click()
                expect(page.get_by_text(ASSOCIATION_NAME, exact=True)).to_be_visible()
                expect(page.get_by_text(re.compile("no dues or legal status established"))).to_be_visible()

                page.get_by_role("button", name="Governing evidence").click()
                expect(page.get_by_role("heading", name="Governing document evidence")).to_be_visible()
                expect(page.get_by_text(re.compile("not verification of governing authority"))).to_be_visible()
                expect(page.get_by_text("No governing documents have been indexed for this property.")).to_be_visible()

                page.get_by_role("button", name="Upload private file").click()
                page.locator("#entity-attachment-file").set_input_files({
                    "name": DOCUMENT_NAME,
                    "mimeType": "application/pdf",
                    "buffer": b"%PDF-1.4\n% E2E synthetic fixture, NOT a governing instrument\n%%EOF\n",
                })
                page.get_by_role("button", name="Upload", exact=True).click()
                expect(page.get_by_role("button", name=DOCUMENT_NAME, exact=True)).to_be_visible()
                page.get_by_role("button", name="Refresh files").click()

                document = page.get_by_label("Document", exact=True)
                expect(document.locator("option")).to_have_count(2)
                document.select_option(index=1)
                page.get_by_label("Staff-supplied document category").select_option(label="Bylaws")
                page.get_by_role("button", name="Record evidence reference").click()
                expect(page.get_by_text("STAFF-SUPPLIED / UNVERIFIED")).to_be_visible()
                expect(page.get_by_text(re.compile("Document authority remains unverified"))).to_be_visible()

                with page.expect_download() as downloaded:
                    page.get_by_role("button", name="Download", exact=True).click()
                assert downloaded.value.suggested_filename == DOCUMENT_NAME

                page.once("dialog", lambda dialog: dialog.accept())
                page.get_by_role("button", name="Archive link").click()
                expect(page.get_by_text(re.compile("Reference archived; no legal action"))).to_be_visible()
                expect(page.get_by_text("No governing documents have been indexed for this property.")).to_be_visible()
                assert _financial_counts() == before
            finally:
                browser.close()
        assert _financial_counts() == before


def test_hoa_staff_procedure_and_case_browser_flow_no_finance() -> None:
    """Exercise the actual staff UI, not an official notice/fine delivery."""
    with _temporarily_release_hoa_ui():
        before = _financial_counts()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            try:
                page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
                page.locator('input[type="email"]').fill(EMAIL)
                page.locator('input[type="password"]').fill(PASSWORD)
                page.get_by_role("button", name="Log In").click()
                page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
                page.goto(
                    f"{BASE_URL}/dashboard/properties/{PROPERTY_ID}",
                    wait_until="domcontentloaded",
                )
                expect(page.get_by_role("heading", name="E2E Test Property")).to_be_visible()
                page.get_by_role("button", name="Compliance", exact=True).click()
                expect(page.get_by_role("heading", name="HOA — recorded associations")).to_be_visible()
                association_name = "E2E Procedure and Case Association"
                page.get_by_label("Association name").fill(association_name)
                page.get_by_role("button", name="Record association").click()
                association = (
                    page.get_by_text(association_name, exact=True).locator("..").locator("..")
                )
                expect(association).to_be_visible()

                _seed_case_recipient(association_name)

                association.get_by_role("button", name="Procedure settings").click()
                policy = association.get_by_role("heading", name="HOA staff procedure configuration").locator("..").locator("..")
                expect(policy.get_by_text("Legal issuance remains disabled")).to_be_visible()
                policy.get_by_label("Proposed cure-tracking days").fill("5")
                policy.get_by_label("Proposed fine cap (not assessed)").fill("45.00")
                policy.get_by_label("Staff draft notice language (not delivered)").fill(
                    "Internal TEST DRAFT only, do not send."
                )
                policy.get_by_role("button", name="Save staff procedure settings").click()
                expect(policy.get_by_text("Staff revision 1")).to_be_visible()
                expect(policy.get_by_text(re.compile("no legal notices, fines or dues are enabled"))).to_be_visible()
                policy.get_by_role("button", name="Close").click()

                association.get_by_role("button", name="Staff observations").click()
                observations = association.get_by_role("heading", name="HOA staff observations").locator("..").locator("..")
                observations.get_by_label("Observation summary").fill("E2E unverified site observation")
                observations.get_by_label("Date observed").fill("2026-09-01")
                observations.get_by_role("button", name="Save staff record").click()
                expect(observations.get_by_text("E2E unverified site observation", exact=False)).to_be_visible()
                observations.get_by_role("button", name="Close").click()

                association.get_by_role("button", name="Staff cases").click()
                cases = association.get_by_role("heading", name="HOA internal review cases").locator("..").locator("..")
                cases.locator("select").last.select_option(index=1)
                cases.get_by_role("button", name="Open internal case").click()
                expect(cases.get_by_text(re.compile("Open staff review"))).to_be_visible()
                cases.get_by_role("button", name="Case follow-ups").click()
                tasks = cases.get_by_role("heading", name=re.compile("Case follow-ups")).locator("..").locator("..")
                tasks.get_by_label("Task title").fill("Inspect synthetic case condition")
                tasks.get_by_label("Assigned staff").select_option(index=1)
                tasks.get_by_label("Internal target date").fill("2026-10-09")
                tasks.get_by_role("button", name="Assign follow-up").click()
                expect(tasks.get_by_text(re.compile("INSPECTION.*Inspect synthetic case condition.*OPEN"))).to_be_visible()
                tasks.get_by_role("button", name="Start follow-up").click()
                tasks.get_by_role("button", name="Complete follow-up").click()
                tasks.get_by_label("Completion note").fill("Synthetic inspection complete")
                tasks.get_by_role("button", name="Save completion").click()
                expect(tasks.get_by_text("Result: Synthetic inspection complete")).to_be_visible()
                assert _financial_counts() == before
                tasks.get_by_role("button", name="Close follow-ups").click()
                cases.get_by_role("button", name="Private case evidence").click()
                evidence = cases.get_by_role("heading", name=re.compile("Private violation evidence")).locator("..").locator("..")
                evidence.get_by_label("Private property evidence file").select_option(label="e2e-private-case-photo.png")
                evidence.get_by_role("button", name="Link private case evidence").click()
                expect(evidence.get_by_text(re.compile("PHOTO.*e2e-private-case-photo"))).to_be_visible()
                assert _financial_counts() == before
                evidence.get_by_role("button", name="Close evidence").click()
                cases.get_by_role("button", name="Potential recipient").click()
                candidate = cases.get_by_role("heading", name=re.compile("Potential violation recipient")).locator("..").locator("..")
                candidate.get_by_label("Potential recipient contact").select_option(label="E2E Verified Case Recipient")
                candidate.get_by_role("button", name="Record potential recipient").click()
                expect(candidate.get_by_text(re.compile("Notice delivery DISABLED"))).to_be_visible()
                assert _financial_counts() == before
                candidate.get_by_role("button", name="Close recipient").click()
                cases.get_by_role("button", name="Advance internal case").click()
                cases.get_by_label("Staff-planned date").fill("2026-09-02")
                cases.get_by_role("button", name="Record staff stage").click()
                expect(cases.get_by_text(re.compile("Notice draft prepared \\(not sent\\)"))).to_be_visible()
                cases.get_by_role("button", name="Private correspondence").click()
                letters = cases.get_by_role("heading", name=re.compile("Private case correspondence")).locator("..").locator("..")
                letters.get_by_label("Internal correspondence subject").fill("Synthetic private reminder")
                letters.get_by_label("Internal correspondence body (never sent)").fill("Internal staff draft, NOT an issued statutory notice.")
                letters.get_by_role("button", name="Record private draft only").click()
                expect(letters.get_by_text(re.compile("STAFF DRAFT.*NOT SENT"))).to_be_visible()
                assert _financial_counts() == before
                letters.get_by_role("button", name="Close correspondence").click()
                cases.get_by_role("button", name="Advance internal case").click()
                cases.get_by_role("button", name="Record staff stage").click()
                expect(cases.get_by_text(re.compile("Tentative cure tracking"))).to_be_visible()
                expect(cases.get_by_text(re.compile("Tentative cure: 2026-09-07"))).to_be_visible()
                cases.get_by_role("button", name="Case history").click()
                history = cases.get_by_role("heading", name="Internal case history").locator("..")
                expect(history.get_by_text(re.compile("NEW.*OPEN"))).to_be_visible()
                expect(history.get_by_text(re.compile("OPEN.*NOTICE DRAFT"))).to_be_visible()
                expect(history.get_by_text(re.compile("NOTICE DRAFT.*CURE TRACKING"))).to_be_visible()
                expect(history.get_by_text(re.compile("Procedure revision 1")).first).to_be_visible()
                expect(history.get_by_text(re.compile("does not deliver a legal notice"))).to_be_visible()
                assert _financial_counts() == before
            finally:
                browser.close()
        assert _financial_counts() == before


def test_hoa_staff_meeting_motion_browser_flow_no_official_vote() -> None:
    """A real browser can prepare an unapproved motion, but cannot cast an official vote."""
    with _temporarily_release_hoa_ui():
        before = _financial_counts()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            try:
                page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
                page.locator('input[type="email"]').fill(EMAIL)
                page.locator('input[type="password"]').fill(PASSWORD)
                page.get_by_role("button", name="Log In").click()
                page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
                page.goto(
                    f"{BASE_URL}/dashboard/properties/{PROPERTY_ID}",
                    wait_until="domcontentloaded",
                )
                expect(page.get_by_role("heading", name="E2E Test Property")).to_be_visible()
                page.get_by_role("button", name="Compliance", exact=True).click()
                expect(page.get_by_role("heading", name="HOA — recorded associations")).to_be_visible()

                association_name = "E2E Meeting Workspace Association"
                page.get_by_label("Association name").fill(association_name)
                page.get_by_role("button", name="Record association").click()
                association = page.get_by_text(association_name, exact=True).locator("..").locator("..")
                association.get_by_role("button", name="Meeting plans").click()
                plans = association.get_by_role("heading", name="HOA staff meeting plans").locator("..").locator("..")
                plans.get_by_label("Staff plan title").fill("E2E proposed agenda")
                plans.get_by_label("Proposed date (not legal notice)").fill("2026-10-14")
                plans.get_by_role("button", name="Save staff plan").click()
                expect(plans.get_by_text("E2E proposed agenda", exact=False)).to_be_visible()

                plans.get_by_role("button", name="Meeting workspace").click()
                workspace = plans.get_by_role(
                    "heading", name="Staff meeting participation and motion preparation"
                ).locator("..").locator("..")
                expect(workspace.get_by_text(re.compile("not official votes"))).to_be_visible()
                workspace.get_by_label("Proposed staff motion").fill("E2E draft landscaping motion")
                workspace.get_by_role("button", name="Save motion draft").click()
                expect(workspace.get_by_text(re.compile("E2E draft landscaping motion"))).to_be_visible()
                expect(workspace.get_by_text(re.compile("PROPOSED ONLY"))).to_be_visible()
                expect(workspace.get_by_text(re.compile("No vote has occurred"))).to_be_visible()
                assert _financial_counts() == before
            finally:
                browser.close()
        assert _financial_counts() == before


def _seed_arc_applicant(association_name: str) -> None:
    if os.environ.get("E2E_SEED_ALLOWED", "").lower() != "true":
        raise RuntimeError("ARC browser test requires disposable E2E database")
    db = SessionLocal()
    try:
        association = db.query(HOAAssociation).filter(
            HOAAssociation.name == association_name,
            HOAAssociation.is_active.is_(True),
        ).one()
        contact = Contact(
            organization_id=association.organization_id,
            display_name="E2E ARC Applicant",
            contact_type="PERSON", is_active=True,
        )
        db.add(contact); db.flush()
        db.add(HOAContactLink(
            organization_id=association.organization_id,
            association_id=association.id,
            property_id=PROPERTY_ID,
            contact_id=contact.id,
            is_active=True,
        ))
        db.commit()
    finally:
        db.close()


def _seed_case_recipient(association_name: str) -> None:
    """Disposable verified member login linked only to this association."""
    if os.environ.get("E2E_SEED_ALLOWED", "").lower() != "true":
        raise RuntimeError("Violation recipient test requires disposable E2E database")
    db = SessionLocal()
    try:
        association = db.query(HOAAssociation).filter(
            HOAAssociation.name == association_name,
            HOAAssociation.is_active.is_(True),
        ).one()
        user = db.query(User).filter(
            User.organization_id == association.organization_id,
            User.email == EMAIL,
        ).one()
        user.is_verified = True
        contact = Contact(
            organization_id=association.organization_id,
            display_name="E2E Verified Case Recipient",
            email=user.email, contact_type="PERSON", is_active=True,
        )
        db.add(contact)
        db.flush()
        db.add(HOAContactLink(
            organization_id=association.organization_id,
            association_id=association.id, property_id=PROPERTY_ID,
            contact_id=contact.id, is_active=True,
        ))
        db.add(EntityAttachment(
            organization_id=association.organization_id,
            entity_type="properties", entity_id=PROPERTY_ID,
            storage_key=f"case-evidence-{association.id}.png",
            original_name="e2e-private-case-photo.png",
            content_type="image/png", size_bytes=100,
            is_active=True, share_with_tenants=False,
            share_with_owners=False,
        ))
        db.commit()
    finally:
        db.close()


def test_hoa_arc_application_review_browser_records_board_approval() -> None:
    with _temporarily_release_hoa_ui():
        before = _financial_counts()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            try:
                page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
                page.locator('input[type="email"]').fill(EMAIL)
                page.locator('input[type="password"]').fill(PASSWORD)
                page.get_by_role("button", name="Log In").click()
                page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
                page.goto(f"{BASE_URL}/dashboard/properties/{PROPERTY_ID}", wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name="E2E Test Property")).to_be_visible()
                page.get_by_role("button", name="Compliance", exact=True).click()

                association_name = "E2E ARC Application Association"
                page.get_by_label("Association name").fill(association_name)
                page.get_by_role("button", name="Record association").click()
                association = page.get_by_text(association_name, exact=True).locator("..").locator("..")
                expect(association).to_be_visible()
                _seed_arc_applicant(association_name)
                # Disposable E2E board login: the actor must be the verified,
                # same-org email owner of a scoped active eligible seat.
                db = SessionLocal()
                try:
                    board_actor = db.query(User).filter(User.email == EMAIL).one()
                    board_actor.is_verified = True
                    assoc = db.query(HOAAssociation).filter(
                        HOAAssociation.name == association_name,
                        HOAAssociation.is_active.is_(True),
                    ).one()
                    contact = Contact(
                        organization_id=assoc.organization_id,
                        display_name="E2E Verified Board Actor",
                        email=EMAIL, contact_type="PERSON", is_active=True,
                    )
                    db.add(contact)
                    db.flush()
                    link = HOAContactLink(
                        organization_id=assoc.organization_id,
                        association_id=assoc.id, property_id=PROPERTY_ID,
                        contact_id=contact.id, is_active=True,
                    )
                    db.add(link)
                    db.flush()
                    db.add(HOABoardSeat(
                        organization_id=assoc.organization_id,
                        association_id=assoc.id, property_id=PROPERTY_ID,
                        contact_link_id=link.id, proposed_role="CHAIR",
                        staff_voting_eligible=True, is_active=True,
                        authorized_user_id=board_actor.id,
                        authorized_by_id=board_actor.id,
                        decision_authorized=True,
                        can_record_offline=True,
                    ))
                    db.commit()
                finally:
                    db.close()

                association.get_by_role("button", name="ARC staff intake").click()
                intake = association.get_by_role("heading", name="ARC staff project intake").locator("..").locator("..")
                intake.get_by_label("Project title").fill("E2E fence application")
                intake.get_by_label("Date noted by staff").fill("2026-09-15")
                intake.get_by_role("button", name="Save staff intake").click()
                expect(intake.get_by_text("E2E fence application", exact=False)).to_be_visible()
                intake.get_by_role("button", name="Application workflow").click()

                workflow = intake.get_by_role("heading", name=re.compile("ARC application and review")).locator("..").locator("..")
                workflow.get_by_label("Applicant contact").select_option(label="E2E ARC Applicant")
                workflow.get_by_label("Application received date").fill("2026-09-16")
                workflow.get_by_role("button", name="Record ARC application").click()
                expect(workflow.get_by_text(re.compile("Awaiting board decision"))).to_be_visible()
                workflow.get_by_role("button", name="Start staff review").click()
                workflow.get_by_role("button", name="Mark ready for decision").click()
                workflow.get_by_role("button", name="Prepare approval").click()
                expect(workflow.get_by_text(re.compile("APPROVE PREPARED FOR BOARD REVIEW"))).to_be_visible()
                workflow.get_by_label("Review note / board decision reason").fill(
                    "E2E recorded board approval"
                )
                workflow.get_by_role("button", name="Record board approval").click()
                expect(workflow.get_by_text(re.compile("Board decision: APPROVED"))).to_be_visible()
                expect(workflow.get_by_text(re.compile("Direct board record"))).to_be_visible()
                expect(workflow.get_by_text(re.compile("Applicant notification: NO VERIFIED RECIPIENT"))).to_be_visible()
                expect(workflow.get_by_role("button", name="Record board approval")).to_have_count(0)
                assert _financial_counts() == before
            finally:
                browser.close()
        assert _financial_counts() == before


def test_hoa_board_role_proposals_browser_flow_never_enables_vote() -> None:
    """Dedicated HOA board UI coverage, using synthetic contacts only."""
    with _temporarily_release_hoa_ui():
        before = _financial_counts()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            try:
                page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
                page.locator('input[type="email"]').fill(EMAIL)
                page.locator('input[type="password"]').fill(PASSWORD)
                page.get_by_role("button", name="Log In").click()
                page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
                page.goto(f"{BASE_URL}/dashboard/properties/{PROPERTY_ID}",
                          wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name="E2E Test Property")).to_be_visible()
                page.get_by_role("button", name="Compliance", exact=True).click()

                association_name = "E2E Board Proposals Association"
                page.get_by_label("Association name").fill(association_name)
                page.get_by_role("button", name="Record association").click()
                association = page.get_by_text(
                    association_name, exact=True,
                ).locator("..").locator("..")
                expect(association).to_be_visible()
                # Explicitly disposable synthetic contact; no actual board identity.
                _seed_arc_applicant(association_name)
                # This disposable E2E fixture explicitly binds the proposed
                # seat to an authenticated, same-org customer login.
                db = SessionLocal()
                try:
                    admin = db.query(User).filter(User.email == EMAIL).one()
                    admin.is_verified = True
                    association_row = db.query(HOAAssociation).filter(
                        HOAAssociation.name == association_name,
                        HOAAssociation.organization_id == admin.organization_id,
                        HOAAssociation.is_active.is_(True),
                    ).one()
                    contact = db.query(Contact).join(
                        HOAContactLink, HOAContactLink.contact_id == Contact.id,
                    ).filter(
                        Contact.organization_id == admin.organization_id,
                        Contact.display_name == "E2E ARC Applicant",
                        HOAContactLink.organization_id == admin.organization_id,
                        HOAContactLink.association_id == association_row.id,
                        HOAContactLink.property_id == PROPERTY_ID,
                        HOAContactLink.is_active.is_(True),
                    ).one()
                    contact.email = admin.email
                    board_login_id = admin.id
                    db.commit()
                finally:
                    db.close()
                association.get_by_role("button", name="Board role proposals").click()
                board = association.get_by_role(
                    "heading", name="Board role and voting rule proposals",
                ).locator("..").locator("..")
                expect(board.get_by_text(re.compile("not themselves authenticated board roles", re.I))).to_be_visible()
                board.get_by_label("Existing scoped HOA contact").select_option(
                    label="E2E ARC Applicant",
                )
                board.get_by_label("Proposed role").select_option("SECRETARY")
                board.get_by_label(re.compile("Staff-proposed voting eligibility")).check()
                board.get_by_role("button", name="Record role proposal").click()
                expect(board.get_by_text("E2E ARC Applicant: SECRETARY", exact=False)).to_be_visible()
                expect(board.get_by_text(re.compile("ARC decision role: Not authorized"))).to_be_visible()
                board.get_by_label("Board login for E2E ARC Applicant").select_option(str(board_login_id))
                board.get_by_label("Designated officer may record offline decisions").check()
                board.get_by_role("button", name="Authorize board login").click()
                expect(board.get_by_text(re.compile("ARC decision role: Authorized login"))).to_be_visible()
                expect(board.get_by_text(re.compile("May record offline board decisions"))).to_be_visible()
                board.get_by_role("button", name="Revoke ARC decision role").click()
                expect(board.get_by_text(re.compile("ARC decision role: Not authorized"))).to_be_visible()
                board.get_by_label("Proposed minimum quorum").fill("3")
                board.get_by_label("Proposed approval threshold").fill("2")
                board.get_by_role("button", name="Save proposed rules").click()
                expect(board.get_by_text(re.compile("Separate motion ballots require their own adoption records"))).to_be_visible()
                expect(board.get_by_text(re.compile("Proposed quorum: 3"))).to_be_visible()
                assert _financial_counts() == before
            finally:
                browser.close()
        assert _financial_counts() == before


def test_hoa_staff_ballot_observations_never_become_legal_votes() -> None:
    with _temporarily_release_hoa_ui():
        before = _financial_counts()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            try:
                page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
                page.locator('input[type="email"]').fill(EMAIL)
                page.locator('input[type="password"]').fill(PASSWORD)
                page.get_by_role("button", name="Log In").click()
                page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
                page.goto(f"{BASE_URL}/dashboard/properties/{PROPERTY_ID}",
                          wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name="E2E Test Property")).to_be_visible()
                page.get_by_role("button", name="Compliance", exact=True).click()

                association_name = "E2E Ballot Report Association"
                page.get_by_label("Association name").fill(association_name)
                page.get_by_role("button", name="Record association").click()
                association = page.get_by_text(
                    association_name, exact=True,
                ).locator("..").locator("..")
                expect(association).to_be_visible()
                _seed_arc_applicant(association_name)
                association.get_by_role("button", name="Board role proposals").click()
                board = association.get_by_role(
                    "heading", name="Board role and voting rule proposals",
                ).locator("..").locator("..")
                board.get_by_label("Existing scoped HOA contact").select_option(
                    label="E2E ARC Applicant",
                )
                board.get_by_label(re.compile("Staff-proposed voting eligibility")).check()
                board.get_by_role("button", name="Record role proposal").click()
                expect(board.get_by_text(re.compile("ARC decision role: Not authorized"))).to_be_visible()
                board.get_by_role("button", name="Close").click()

                association.get_by_role("button", name="Meeting plans").click()
                meetings = association.get_by_role(
                    "heading", name="HOA staff meeting plans",
                ).locator("..").locator("..")
                meetings.get_by_label("Staff plan title").fill("Synthetic ballot meeting")
                meetings.get_by_label("Proposed date (not legal notice)").fill("2026-11-12")
                meetings.get_by_role("button", name="Save staff plan").click()
                meetings.get_by_role("button", name="Meeting workspace").click()
                workspace = meetings.get_by_role(
                    "heading", name="Staff meeting participation and motion preparation",
                ).locator("..").locator("..")
                workspace.get_by_label("Proposed staff motion").fill(
                    "Synthetic ballot motion, not an adopted resolution"
                )
                workspace.get_by_role("button", name="Save motion draft").click()
                workspace.get_by_role("button", name="Staff ballot records").click()
                ballots = workspace.get_by_role(
                    "heading", name="Staff-reported ballot observations",
                ).locator("..").locator("..")
                expect(ballots.get_by_text(re.compile("not a ballot cast", re.I))).to_be_visible()
                ballots.get_by_label("Staff-proposed eligible contact").select_option(
                    label="E2E ARC Applicant (DIRECTOR)"
                )
                ballots.get_by_label("Staff-reported choice").select_option("FOR")
                ballots.get_by_role("button", name="Record staff observation").click()
                expect(ballots.get_by_text("E2E ARC Applicant · FOR · UNVERIFIED")).to_be_visible()
                expect(ballots.get_by_text(re.compile("No legally effective vote occurred"))).to_be_visible()
                assert _financial_counts() == before
            finally:
                browser.close()
        assert _financial_counts() == before


def test_hoa_unissued_dues_history_browser_replay_and_void() -> None:
    """A dedicated end-to-end HOA workflow never turns a contact into a debtor."""
    with _temporarily_release_hoa_ui():
        before = _financial_counts()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            try:
                page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
                page.locator('input[type="email"]').fill(EMAIL)
                page.locator('input[type="password"]').fill(PASSWORD)
                page.get_by_role("button", name="Log In").click()
                page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
                page.goto(f"{BASE_URL}/dashboard/properties/{PROPERTY_ID}",
                          wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name="E2E Test Property")).to_be_visible()
                page.get_by_role("button", name="Compliance", exact=True).click()
                association_name = "E2E Unissued Dues History Association"
                page.get_by_label("Association name").fill(association_name)
                page.get_by_role("button", name="Record association").click()
                association = page.get_by_text(
                    association_name, exact=True,
                ).locator("..").locator("..")
                expect(association).to_be_visible()
                _seed_arc_applicant(association_name)

                association.get_by_role("button", name="Draft assessments").click()
                drafts = association.get_by_role(
                    "heading", name="Assessment planning drafts",
                ).locator("..").locator("..")
                drafts.get_by_label("Proposal title").fill("Synthetic recurring dues")
                drafts.get_by_label("Proposed amount (not billed)").fill("75.00")
                drafts.get_by_label("Proposed first date (not a due date)").fill("2028-01-31")
                drafts.get_by_role("button", name="Save draft only").click()
                expect(drafts.get_by_text("Synthetic recurring dues", exact=False)).to_be_visible()
                drafts.get_by_role("button", name="Suggested payer").click()
                payer = drafts.get_by_role(
                    "heading", name="Suggested assessment contact",
                ).locator("..").locator("..")
                payer.get_by_label("Staff-suggested contact").select_option(
                    label="E2E ARC Applicant",
                )
                payer.get_by_role("button", name="Save staff reference").click()
                expect(payer.get_by_text(re.compile("Issue charge: DISABLED"))).to_be_visible()

                drafts.get_by_role("button", name="Planning history").click()
                history = drafts.get_by_role(
                    "heading", name="Unissued assessment planning history",
                ).locator("..").locator("..")
                history.get_by_label("From").fill("2028-01-01")
                history.get_by_label("Through").fill("2028-03-31")
                history.get_by_role("button", name="Record unissued schedule").click()
                expect(history.get_by_text(re.compile("3 new planning periods"))).to_be_visible()
                expect(history.get_by_text(re.compile("2028-02-29"))).to_be_visible()
                history.get_by_role("button", name="Record unissued schedule").click()
                expect(history.get_by_text(re.compile("0 new planning periods"))).to_be_visible()
                history.get_by_role("button", name="Posting readiness").first.click()
                expect(history.get_by_text(re.compile("Posting and reversal DISABLED"))).to_be_visible()
                expect(history.get_by_text(re.compile("governing authority unverified"))).to_be_visible()
                assert _financial_counts() == before
                page.once("dialog", lambda dialog: dialog.accept())
                history.get_by_role("button", name="Void draft").first.click()
                expect(history.get_by_text(re.compile("This is not a financial reversal"))).to_be_visible()
                expect(history.get_by_text(re.compile("2028-01-31.*VOIDED"))).to_be_visible()
                assert _financial_counts() == before
            finally:
                browser.close()
        assert _financial_counts() == before


def test_hoa_reserve_movement_staff_browser_never_posts_transfer() -> None:
    with _temporarily_release_hoa_ui():
        before = _financial_counts()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            try:
                page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
                page.locator('input[type="email"]').fill(EMAIL)
                page.locator('input[type="password"]').fill(PASSWORD)
                page.get_by_role("button", name="Log In").click()
                page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
                page.goto(f"{BASE_URL}/dashboard/properties/{PROPERTY_ID}",
                          wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name="E2E Test Property")).to_be_visible()
                page.get_by_role("button", name="Compliance", exact=True).click()
                name = "E2E Reserve Movement Planning Association"
                page.get_by_label("Association name").fill(name)
                page.get_by_role("button", name="Record association").click()
                association = page.get_by_text(name, exact=True).locator("..").locator("..")
                expect(association).to_be_visible()

                # Synthetic accounts on disposable E2E DB, never a bank credential.
                db = SessionLocal()
                try:
                    assoc = db.query(HOAAssociation).filter(
                        HOAAssociation.name == name,
                        HOAAssociation.is_active.is_(True),
                    ).one()
                    db.add_all([
                        GLAccount(organization_id=assoc.organization_id,
                                  gl_number="E2ERE1", name="E2E Reserve Cash",
                                  account_type="ASSET", include_on_cash_flow=True, is_active=True),
                        GLAccount(organization_id=assoc.organization_id,
                                  gl_number="E2EOP1", name="E2E Operating Cash",
                                  account_type="ASSET", include_on_cash_flow=True, is_active=True),
                    ])
                    db.commit()
                finally:
                    db.close()

                association.get_by_role("button", name="Reserve book").click()
                book = association.get_by_role(
                    "heading", name="HOA reserve book readiness",
                ).locator("..").locator("..")
                book.get_by_label("Existing same-organization GL").select_option(
                    label="E2ERE1 · E2E Reserve Cash",
                )
                book.get_by_role("button", name="Record reserve GL reference").click()
                expect(book.get_by_text(re.compile("Staff GL reference recorded"))).to_be_visible()
                movement = book.get_by_role(
                    "heading", name="Reserve movement preparation",
                ).locator("..").locator("..")
                movement.get_by_label("Existing same-org counterparty cash GL").select_option(
                    label="E2EOP1 · E2E Operating Cash",
                )
                movement.get_by_label("Proposed date").fill("2028-03-01")
                movement.get_by_label("Proposed amount").fill("250.00")
                movement.get_by_label("Staff memo").fill("Synthetic unissued reserve transfer")
                movement.get_by_role("button", name="Prepare unissued movement").click()
                expect(movement.get_by_text(re.compile("No funds were moved"))).to_be_visible()
                expect(movement.get_by_text(re.compile("Synthetic unissued reserve transfer"))).to_be_visible()
                assert _financial_counts() == before
                page.once("dialog", lambda dialog: dialog.accept())
                movement.get_by_role("button", name="Cancel draft").click()
                expect(movement.get_by_text(re.compile("no financial transfer or reversal"))).to_be_visible()
                assert _financial_counts() == before
            finally:
                browser.close()
        assert _financial_counts() == before
