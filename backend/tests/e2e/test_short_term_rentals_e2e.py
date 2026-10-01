"""Authenticated Phase 4.12 Short-term Rentals customer-flow coverage."""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
import os
import re

import pytest

import init_db  # noqa: F401

playwright_sync = pytest.importorskip("playwright.sync_api")
expect = playwright_sync.expect
sync_playwright = playwright_sync.sync_playwright

from app.core.database import SessionLocal
from app.models.property import Property, Unit
from app.models.release_gate import ReleaseGate, ReleaseStage
from app.models.short_term_rental import ShortTermRentalChannel, ShortTermRentalNightlyPrice, ShortTermRentalTurnover
from app.models.user import User

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
EMAIL = os.environ["E2E_ADMIN_EMAIL"]
PASSWORD = os.environ["E2E_ADMIN_PASSWORD"]
PROPERTY_ID = 900001


@contextmanager
def _short_term_rental_fixture():
    if os.environ.get("E2E_SEED_ALLOWED", "").lower() != "true":
        raise RuntimeError("Short-term Rentals browser test requires a disposable E2E database")

    db = SessionLocal()
    gate = db.query(ReleaseGate).filter(
        ReleaseGate.key == "release.properties.short_term_rentals"
    ).one_or_none()
    previous_stage = gate.stage if gate is not None else None
    created_gate = False
    unit = None
    try:
        if gate is None:
            gate = ReleaseGate(
                key="release.properties.short_term_rentals",
                stage=ReleaseStage.ALL_ORGS,
            )
            db.add(gate)
            created_gate = True
        else:
            gate.stage = ReleaseStage.ALL_ORGS

        actor = db.query(User).filter(User.email == EMAIL).one()
        prop = db.get(Property, PROPERTY_ID)
        if prop is None or prop.organization_id != actor.organization_id:
            raise RuntimeError("Disposable Short-term Rentals E2E property is unavailable")

        unit = Unit(
            property_id=prop.id,
            unit_number="STR-E2E-101",
            bedrooms=1,
            bathrooms=1,
            monthly_rent=Decimal("1400"),
            is_active=True,
        )
        db.add(unit)
        db.commit()
        yield
    finally:
        db.rollback()
        if unit is not None:
            db.query(ShortTermRentalTurnover).filter(
                ShortTermRentalTurnover.unit_id == unit.id
            ).delete(synchronize_session=False)
            db.query(ShortTermRentalNightlyPrice).filter(
                ShortTermRentalNightlyPrice.unit_id == unit.id
            ).delete(synchronize_session=False)
        db.query(ShortTermRentalChannel).filter(
            ShortTermRentalChannel.property_id == PROPERTY_ID,
            ShortTermRentalChannel.label == "E2E Airbnb",
        ).delete(synchronize_session=False)
        if unit is not None:
            persisted = db.get(Unit, unit.id)
            if persisted is not None:
                db.delete(persisted)
        if created_gate and gate is not None:
            persisted_gate = db.get(ReleaseGate, gate.id)
            if persisted_gate is not None:
                db.delete(persisted_gate)
        elif gate is not None:
            gate.stage = previous_stage
        db.commit()
        db.close()


def test_short_term_rentals_property_tab_end_to_end():
    with _short_term_rental_fixture():
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            try:
                page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
                page.locator('input[type="email"]').fill(EMAIL)
                page.locator('input[type="password"]').fill(PASSWORD)
                page.get_by_role("button", name="Log In").click()
                page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)

                page.goto(
                    f"{BASE_URL}/dashboard/properties/{PROPERTY_ID}",
                    wait_until="domcontentloaded",
                )
                page.get_by_role("button", name="Short-term Rentals", exact=True).click()
                expect(page.get_by_role("heading", name="Short-term Rentals")).to_be_visible()

                page.get_by_label("Short-term rental provider").select_option("AIRBNB")
                page.get_by_label("Short-term rental channel label").fill("E2E Airbnb")
                page.get_by_label("Short-term rental external listing ID").fill("AIR-E2E-101")
                page.get_by_role("button", name="Add channel reference").click()
                expect(page.get_by_text("Staff-recorded channel reference created. No provider connection was established.")).to_be_visible()
                expect(
                    page.get_by_label("Short-term rental channel list").get_by_text(
                        re.compile(r"AIRBNB.*E2E Airbnb.*AIR-E2E-101")
                    )
                ).to_be_visible()

                page.get_by_label("Nightly price unit").select_option(label="STR-E2E-101")
                page.get_by_label("Nightly price date").fill("2026-10-20")
                page.get_by_label("Nightly price rate").fill("199.00")
                page.get_by_label("Nightly price minimum stay").fill("2")
                page.get_by_role("button", name="Record nightly price").click()
                expect(page.get_by_text("Nightly price recorded locally. No provider price was changed.")).to_be_visible()
                expect(
                    page.get_by_label("Nightly price list").get_by_text(
                        re.compile(r"STR-E2E-101.*2026-10-20.*USD 199")
                    )
                ).to_be_visible()

                page.get_by_label("Turnover unit").select_option(label="STR-E2E-101")
                page.get_by_label("Turnover start").fill("2026-10-21T11:00")
                page.get_by_label("Turnover end").fill("2026-10-21T15:00")
                page.get_by_role("button", name="Record turnover schedule").click()
                expect(page.get_by_text("Turnover schedule recorded. Linked work orders or inspections were not modified.")).to_be_visible()
                turnover_list = page.get_by_label("Turnover schedule list")
                expect(turnover_list.get_by_text("STR-E2E-101", exact=True)).to_be_visible()
                expect(turnover_list.get_by_text("SCHEDULED", exact=True)).to_be_visible()
            finally:
                browser.close()
