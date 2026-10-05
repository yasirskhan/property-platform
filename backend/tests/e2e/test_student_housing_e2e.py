"""Authenticated Phase 4.10 Student Housing browser coverage."""
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
from app.models.lease import Lease
from app.models.property import (
    Property,
    StudentAcademicCycle,
    StudentBed,
    StudentGuarantor,
    Unit,
)
from app.models.release_gate import ReleaseGate, ReleaseStage
from app.models.user import User, UserRole

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")
PROPERTY_ID = 900001


@contextmanager
def _student_housing_fixture():
    if os.environ.get("E2E_SEED_ALLOWED", "").lower() != "true":
        raise RuntimeError("Student Housing browser test requires a disposable E2E database")

    db = SessionLocal()
    gate = (
        db.query(ReleaseGate)
        .filter(ReleaseGate.key == "release.properties.student_housing")
        .one_or_none()
    )
    previous_stage = gate.stage if gate is not None else None
    created_gate = False
    unit = None
    tenant = None

    try:
        if gate is None:
            gate = ReleaseGate(
                key="release.properties.student_housing",
                stage=ReleaseStage.ALL_ORGS,
            )
            db.add(gate)
            created_gate = True
        else:
            gate.stage = ReleaseStage.ALL_ORGS

        actor = db.query(User).filter(User.email == EMAIL).one()
        prop = db.get(Property, PROPERTY_ID)
        if prop is None or prop.organization_id != actor.organization_id:
            raise RuntimeError("Disposable Student Housing E2E property is unavailable")

        unit = Unit(
            property_id=prop.id,
            unit_number="STUDENT-E2E-101",
            bedrooms=2,
            bathrooms=1,
            monthly_rent=Decimal("1400"),
            is_active=True,
        )
        tenant = User(
            organization_id=actor.organization_id,
            role=UserRole.TENANT,
            first_name="Student",
            last_name="E2E",
            email="student-housing-e2e@example.com",
            hashed_password="not-used",
            is_active=True,
        )
        db.add_all([unit, tenant])
        db.commit()
        yield unit.id, tenant.id
    finally:
        db.rollback()
        e2e_bed = (
            db.query(StudentBed)
            .filter(
                StudentBed.property_id == PROPERTY_ID,
                StudentBed.bed_label == "Bed E2E-A",
            )
            .one_or_none()
        )
        if e2e_bed is not None:
            lease_ids = [
                row[0]
                for row in db.query(Lease.id)
                .filter(Lease.student_bed_id == e2e_bed.id)
                .all()
            ]
            if lease_ids:
                (
                    db.query(StudentGuarantor)
                    .filter(StudentGuarantor.lease_id.in_(lease_ids))
                    .delete(synchronize_session=False)
                )
                db.query(Lease).filter(Lease.id.in_(lease_ids)).delete(
                    synchronize_session=False
                )
                db.flush()
            db.delete(e2e_bed)
        db.query(StudentAcademicCycle).filter(
            StudentAcademicCycle.property_id == PROPERTY_ID,
            StudentAcademicCycle.name == "E2E Academic Year",
        ).delete(synchronize_session=False)

        if unit is not None:
            persisted_unit = db.get(Unit, unit.id)
            if persisted_unit is not None:
                db.delete(persisted_unit)
        if tenant is not None:
            persisted_tenant = db.get(User, tenant.id)
            if persisted_tenant is not None:
                db.delete(persisted_tenant)

        if created_gate and gate is not None:
            persisted_gate = db.get(ReleaseGate, gate.id)
            if persisted_gate is not None:
                db.delete(persisted_gate)
        elif gate is not None:
            gate.stage = previous_stage

        db.commit()
        db.close()


def test_student_housing_property_tab_end_to_end():
    with _student_housing_fixture():
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
                expect(page.get_by_role("heading", name="E2E Test Property")).to_be_visible()
                page.get_by_role("button", name="Student Housing", exact=True).click()
                expect(
                    page.get_by_role("heading", name="Student Housing")
                ).to_be_visible()

                page.get_by_label("Academic cycle name").fill("E2E Academic Year")
                page.get_by_label("Academic cycle start date").fill("2026-08-20")
                page.get_by_label("Academic cycle end date").fill("2027-05-15")
                page.get_by_role("button", name="Create academic cycle").click()
                expect(page.get_by_text("Academic cycle created.")).to_be_visible()
                expect(
                    page.get_by_label("Academic cycle list").get_by_text(
                        "E2E Academic Year", exact=True
                    )
                ).to_be_visible()

                page.get_by_label("Student bed unit").select_option(label="STUDENT-E2E-101")
                page.get_by_label("Student bed label").fill("Bed E2E-A")
                page.get_by_role("button", name="Create bed").click()
                expect(page.get_by_text("Bed inventory created.")).to_be_visible()
                expect(page.get_by_text(re.compile("Bed E2E-A.*Unit STUDENT-E2E-101"))).to_be_visible()

                page.get_by_label("Bed lease bed").select_option(label="STUDENT-E2E-101 · Bed E2E-A")
                page.get_by_label("Bed lease tenant").select_option(
                    label="Student E2E · student-housing-e2e@example.com"
                )
                page.get_by_label("Bed lease academic cycle").select_option(label="E2E Academic Year")
                page.get_by_label("Bed lease start date").fill("2026-08-20")
                page.get_by_label("Bed lease end date").fill("2027-05-15")
                page.get_by_label("Bed lease monthly rent").fill("650")
                page.get_by_label("Bed lease security deposit").fill("300")
                page.get_by_label("Bed lease due day").fill("1")
                page.get_by_role("button", name="Create draft bed lease").click()
                expect(
                    page.get_by_text(
                        "Draft by-the-bed lease created in the standard lease lifecycle."
                    )
                ).to_be_visible()
                lease_list = page.get_by_label("Student bed lease list")
                expect(lease_list.get_by_text("Student E2E", exact=True)).to_be_visible()
                expect(lease_list.get_by_text("draft", exact=True)).to_be_visible()

                page.get_by_label("Guarantor bed lease").select_option(index=1)
                page.get_by_label("Guarantor full name").fill("Parent E2E")
                page.get_by_label("Guarantor email").fill("parent-e2e@example.com")
                page.get_by_label("Guarantor relationship").fill("Parent")
                page.get_by_role("button", name="Create guarantor workflow").click()
                expect(page.get_by_text("Guarantor workflow record created.")).to_be_visible()

                row = page.get_by_label("Guarantor workflow list").get_by_text(
                    re.compile("Parent E2E.*DRAFT")
                )
                expect(row).to_be_visible()

                page.get_by_role("button", name="Mark requested").click()
                expect(
                    page.get_by_text("Guarantor request marked as externally requested.")
                ).to_be_visible()
                expect(
                    page.get_by_label("Guarantor workflow list").get_by_text(
                        re.compile("Parent E2E.*REQUESTED")
                    )
                ).to_be_visible()

                page.get_by_role("button", name="Record document received").click()
                expect(
                    page.get_by_text("Guarantor document receipt recorded.")
                ).to_be_visible()
                expect(
                    page.get_by_label("Guarantor workflow list").get_by_text(
                        re.compile("Parent E2E.*DOCUMENT_RECEIVED")
                    )
                ).to_be_visible()
            finally:
                browser.close()
