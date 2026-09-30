"""Authenticated RUBs allocation history and finance-neutral true-up browser coverage."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
import os
import re

import pytest

import init_db  # noqa: F401

playwright_sync = pytest.importorskip("playwright.sync_api")
expect = playwright_sync.expect
sync_playwright = playwright_sync.sync_playwright

from app.core.database import SessionLocal
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, Unit
from app.models.release_gate import ReleaseGate, ReleaseStage
from app.models.user import User
from app.models.utility import (
    PaidBy,
    PropertyUtility,
    UtilityBill,
    UtilityType,
)

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")
PROPERTY_ID = 900001


@contextmanager
def _rubs_fixture():
    if os.environ.get("E2E_SEED_ALLOWED", "").lower() != "true":
        raise RuntimeError("RUBs browser test requires a disposable E2E database")

    db = SessionLocal()
    gate = (
        db.query(ReleaseGate)
        .filter(ReleaseGate.key == "release.properties.rubs")
        .one_or_none()
    )
    previous_stage = gate.stage if gate is not None else None
    created_gate = False
    utility = None
    units = []

    try:
        if gate is None:
            gate = ReleaseGate(
                key="release.properties.rubs",
                stage=ReleaseStage.ALL_ORGS,
            )
            db.add(gate)
            created_gate = True
        else:
            gate.stage = ReleaseStage.ALL_ORGS

        prop = db.get(Property, PROPERTY_ID)
        actor = db.query(User).filter(User.email == EMAIL).one()
        if prop is None or prop.organization_id != actor.organization_id:
            raise RuntimeError("Disposable RUBs E2E property is unavailable")

        units = [
            Unit(
                property_id=prop.id,
                unit_number="RUBS-E2E-A",
                bedrooms=1,
                bathrooms=1,
                square_feet=600,
                monthly_rent=Decimal("1000"),
                is_active=True,
            ),
            Unit(
                property_id=prop.id,
                unit_number="RUBS-E2E-B",
                bedrooms=1,
                bathrooms=1,
                square_feet=400,
                monthly_rent=Decimal("1000"),
                is_active=True,
            ),
        ]
        db.add_all(units)
        db.flush()

        utility = PropertyUtility(
            property_id=prop.id,
            utility_type=UtilityType.WATER,
            company_name="RUBs E2E Shared Water",
            paid_by=PaidBy.SHARED,
            is_active=True,
        )
        db.add(utility)
        db.flush()
        db.add(
            UtilityBill(
                utility_id=utility.id,
                billing_period_start=date(2026, 9, 1),
                billing_period_end=date(2026, 9, 30),
                amount=Decimal("100.01"),
            )
        )
        db.commit()
        yield utility.id
    finally:
        db.rollback()
        if utility is not None:
            persisted_utility = db.get(PropertyUtility, utility.id)
            if persisted_utility is not None:
                db.delete(persisted_utility)
        for unit in units:
            persisted_unit = db.get(Unit, unit.id)
            if persisted_unit is not None:
                db.delete(persisted_unit)

        if created_gate and gate is not None:
            persisted_gate = db.get(ReleaseGate, gate.id)
            if persisted_gate is not None:
                db.delete(persisted_gate)
        elif gate is not None:
            gate.stage = previous_stage

        db.commit()
        db.close()


def _finance_counts():
    db = SessionLocal()
    try:
        return db.query(Charge).count(), db.query(GLTransaction).count()
    finally:
        db.close()


def test_rubs_allocation_rule_authorize_and_preview_is_non_posting():
    with _rubs_fixture() as utility_id:
        before = _finance_counts()

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
                page.get_by_role("button", name="RUBs", exact=True).click()
                expect(
                    page.get_by_role(
                        "heading",
                        name="RUBs — utility allocation readiness",
                    )
                ).to_be_visible()

                page.get_by_label("Shared utility for meter readings").select_option(
                    str(utility_id)
                )
                expect(
                    page.get_by_role("heading", name="Allocation rule and preview")
                ).to_be_visible()

                page.get_by_label("Effective date").fill("2026-09-01")
                page.get_by_label(re.compile("Unit RUBS-E2E-A")).check()
                page.get_by_label(re.compile("Unit RUBS-E2E-B")).check()
                page.get_by_role(
                    "button",
                    name="Create draft rule revision",
                ).click()
                expect(
                    page.get_by_text(
                        re.compile("Draft rule revision 1 recorded")
                    )
                ).to_be_visible()

                page.get_by_role(
                    "button",
                    name="Authorize revision 1",
                ).click()
                expect(
                    page.get_by_text(
                        re.compile("Rule revision 1 explicitly authorized")
                    )
                ).to_be_visible()

                page.get_by_role(
                    "button",
                    name="Preview allocation",
                ).click()
                expect(
                    page.get_by_text(
                        "Finance-neutral preview: USD 100.01 of USD 100.01"
                    )
                ).to_be_visible()
                expect(
                    page.get_by_text(
                        re.compile("Round each raw unit share down")
                    )
                ).to_be_visible()

                page.get_by_role(
                    "button",
                    name="Save reviewed allocation snapshot",
                ).click()
                expect(
                    page.get_by_text(
                        re.compile("Reviewed allocation snapshot #")
                    )
                ).to_be_visible()

                page.get_by_label("True-up period start").fill("2026-09-01")
                page.get_by_label("True-up period end").fill("2026-09-30")
                page.get_by_label("Year-end actual total").fill("110.01")
                page.get_by_label("True-up weight for unit RUBS-E2E-A").fill("600")
                page.get_by_label("True-up weight for unit RUBS-E2E-B").fill("400")
                page.get_by_role(
                    "button",
                    name="Preview year-end true-up",
                ).click()
                expect(
                    page.get_by_text(
                        re.compile("Finance-neutral true-up: USD 100.01 prior to USD 110.01")
                    )
                ).to_be_visible()
            finally:
                browser.close()

        assert _finance_counts() == before
