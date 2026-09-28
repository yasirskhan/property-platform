"""Browser contract: HOA evidence remains a private, unverified staff reference.

This test uses a synthetic document in the disposable E2E database. It does
not supply, approve, or interpret any actual HOA governing instrument.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
import re

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")
expect = playwright_sync.expect
sync_playwright = playwright_sync.sync_playwright

from app.core.database import SessionLocal
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
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
