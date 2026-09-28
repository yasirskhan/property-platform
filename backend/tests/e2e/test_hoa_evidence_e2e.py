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
from app.models.contact import Contact
from app.models.hoa_association import HOAAssociation, HOAContactLink
from app.models.release_gate import ReleaseGate, ReleaseStage

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
    try:
        for key in ("release.properties.compliance", "release.documents.attachments"):
            gate = db.query(ReleaseGate).filter(ReleaseGate.key == key).one_or_none()
            if gate is None:
                gate = ReleaseGate(key=key, stage=ReleaseStage.ALL_ORGS)
                db.add(gate)
                db.flush()
                previous[key] = (gate.id, None)
            else:
                previous[key] = (gate.id, gate.stage)
                gate.stage = ReleaseStage.ALL_ORGS
        db.commit()
        yield
    finally:
        db.rollback()
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
                cases.get_by_role("button", name="Advance internal case").click()
                cases.get_by_label("Staff-planned date").fill("2026-09-02")
                cases.get_by_role("button", name="Record staff stage").click()
                expect(cases.get_by_text(re.compile("Notice draft prepared \\(not sent\\)"))).to_be_visible()
                cases.get_by_role("button", name="Advance internal case").click()
                cases.get_by_role("button", name="Record staff stage").click()
                expect(cases.get_by_text(re.compile("Tentative cure tracking"))).to_be_visible()
                expect(cases.get_by_text(re.compile("Tentative cure: 2026-09-07"))).to_be_visible()
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


def test_hoa_arc_application_review_browser_flow_prepares_no_effective_decision() -> None:
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
                expect(workflow.get_by_text(re.compile("Effective legal decision: NO"))).to_be_visible()
                workflow.get_by_role("button", name="Start staff review").click()
                workflow.get_by_role("button", name="Mark ready for decision").click()
                workflow.get_by_role("button", name="Prepare approval").click()
                expect(workflow.get_by_text(re.compile("APPROVE PREPARED ONLY"))).to_be_visible()
                expect(workflow.get_by_text(re.compile("Effective legal decision: NO"))).to_be_visible()
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
                association.get_by_role("button", name="Board role proposals").click()
                board = association.get_by_role(
                    "heading", name="Board role and voting rule proposals",
                ).locator("..").locator("..")
                expect(board.get_by_text(re.compile("not authenticated board", re.I))).to_be_visible()
                board.get_by_label("Existing scoped HOA contact").select_option(
                    label="E2E ARC Applicant",
                )
                board.get_by_label("Proposed role").select_option("SECRETARY")
                board.get_by_label(re.compile("Staff-proposed voting eligibility")).check()
                board.get_by_role("button", name="Record role proposal").click()
                expect(board.get_by_text("E2E ARC Applicant: SECRETARY", exact=False)).to_be_visible()
                expect(board.get_by_text("Unverified. Vote disabled.")).to_be_visible()
                board.get_by_label("Proposed minimum quorum").fill("3")
                board.get_by_label("Proposed approval threshold").fill("2")
                board.get_by_role("button", name="Save proposed rules").click()
                expect(board.get_by_text(re.compile("No verified board authority"))).to_be_visible()
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
                expect(board.get_by_text("Unverified. Vote disabled.")).to_be_visible()
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
                history.get_by_role("button", name="Void draft").first.click()
                expect(history.get_by_text(re.compile("This is not a financial reversal"))).to_be_visible()
                expect(history.get_by_text(re.compile("2028-01-31.*VOIDED"))).to_be_visible()
                assert _financial_counts() == before
            finally:
                browser.close()
        assert _financial_counts() == before
