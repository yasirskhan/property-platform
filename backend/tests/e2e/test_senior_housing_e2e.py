"""Authenticated Phase 4.11 Senior Housing customer-surface coverage."""
from __future__ import annotations

from contextlib import contextmanager
import os
import re

import pytest

import init_db  # noqa: F401

playwright_sync = pytest.importorskip("playwright.sync_api")
expect = playwright_sync.expect
sync_playwright = playwright_sync.sync_playwright

from app.core.database import SessionLocal
from app.models.property import Property
from app.models.release_gate import ReleaseGate, ReleaseStage
from app.models.senior_housing import SeniorAgeRestriction, SeniorCareResource, SeniorHUDProgram
from app.models.user import User

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")
PROPERTY_ID = 900001


@contextmanager
def _senior_housing_fixture():
    if os.environ.get("E2E_SEED_ALLOWED", "").lower() != "true":
        raise RuntimeError("Senior Housing browser test requires a disposable E2E database")

    db = SessionLocal()
    gate = db.query(ReleaseGate).filter(
        ReleaseGate.key == "release.properties.senior_housing"
    ).one_or_none()
    previous_stage = gate.stage if gate is not None else None
    created_gate = False

    try:
        if gate is None:
            gate = ReleaseGate(
                key="release.properties.senior_housing",
                stage=ReleaseStage.ALL_ORGS,
            )
            db.add(gate)
            created_gate = True
        else:
            gate.stage = ReleaseStage.ALL_ORGS

        actor = db.query(User).filter(User.email == EMAIL).one()
        prop = db.get(Property, PROPERTY_ID)
        if prop is None or prop.organization_id != actor.organization_id:
            raise RuntimeError("Disposable Senior Housing E2E property is unavailable")

        db.commit()
        yield
    finally:
        db.rollback()
        db.query(SeniorHUDProgram).filter(
            SeniorHUDProgram.property_id == PROPERTY_ID,
            SeniorHUDProgram.label == "E2E HUD 202 reference",
        ).delete(synchronize_session=False)
        db.query(SeniorCareResource).filter(
            SeniorCareResource.property_id == PROPERTY_ID,
            SeniorCareResource.provider_name == "E2E Community Resource Desk",
        ).delete(synchronize_session=False)
        db.query(SeniorAgeRestriction).filter(
            SeniorAgeRestriction.property_id == PROPERTY_ID,
            SeniorAgeRestriction.label == "E2E 55+ recorded restriction",
        ).delete(synchronize_session=False)

        if created_gate and gate is not None:
            persisted_gate = db.get(ReleaseGate, gate.id)
            if persisted_gate is not None:
                db.delete(persisted_gate)
        elif gate is not None:
            gate.stage = previous_stage

        db.commit()
        db.close()


def test_senior_housing_property_tab_end_to_end():
    with _senior_housing_fixture():
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            try:
                page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
                page.locator('input[type="email"]').fill(EMAIL)
                page.locator('input[type="password"]').fill(PASSWORD)
                page.get_by_role("button", name="Log In").click()
                page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
                expect(page.get_by_text(EMAIL, exact=True)).to_be_visible()

                page.goto(
                    f"{BASE_URL}/dashboard/properties/{PROPERTY_ID}",
                    wait_until="domcontentloaded",
                )
                page.get_by_role("button", name="Senior Housing", exact=True).click()
                expect(page.get_by_role("heading", name="Senior Housing")).to_be_visible()
                expect(
                    page.get_by_text(re.compile("do not determine resident eligibility"))
                ).to_be_visible()

                page.get_by_label("Senior restriction type").select_option("AGE_55_PLUS")
                page.get_by_label("Senior restriction label").fill("E2E 55+ recorded restriction")
                page.get_by_label("Senior restriction authority").fill("E2E governing reference")
                page.get_by_label("Senior restriction reference").fill("E2E-55-REF")
                page.get_by_role("button", name="Record age-restriction reference").click()
                expect(
                    page.get_by_text("Age-restriction reference recorded; resident eligibility was not determined.")
                ).to_be_visible()
                expect(
                    page.get_by_label("Senior age restriction list").get_by_text(
                        re.compile("E2E 55\+ recorded restriction.*AGE_55_PLUS")
                    )
                ).to_be_visible()

                page.get_by_label("Senior care resource type").select_option("CARE_COORDINATION")
                page.get_by_label("Senior care provider name").fill("E2E Community Resource Desk")
                page.get_by_label("Senior care contact name").fill("Program Contact")
                page.get_by_role("button", name="Record care resource").click()
                expect(
                    page.get_by_text("Care resource recorded as a property-level directory reference.")
                ).to_be_visible()
                expect(
                    page.get_by_label("Senior care resource list").get_by_text(
                        re.compile("E2E Community Resource Desk.*CARE_COORDINATION")
                    )
                ).to_be_visible()

                page.get_by_label("Senior HUD program type").select_option("HUD_202")
                page.get_by_label("Senior HUD label").fill("E2E HUD 202 reference")
                page.get_by_label("Senior HUD readiness status").select_option("EVIDENCE_RECORDED")
                page.get_by_label("Senior HUD evidence reference").fill("E2E evidence index")
                page.get_by_label("Senior HUD evidence date").fill("2026-09-30")
                page.get_by_role("button", name="Record HUD 202/811 reference").click()
                expect(
                    page.get_by_text("HUD 202/811 reference recorded; HUD eligibility or funding was not certified.")
                ).to_be_visible()
                expect(
                    page.get_by_label("Senior HUD program list").get_by_text(
                        re.compile("E2E HUD 202 reference.*HUD_202.*EVIDENCE_RECORDED")
                    )
                ).to_be_visible()
            finally:
                browser.close()
