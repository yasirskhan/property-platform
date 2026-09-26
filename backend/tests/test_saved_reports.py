from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
import app.routers.reporting as reporting
from app.core.database import Base
from app.models.saved_report import SavedReport
from app.models.user import Organization, User, UserRole
from app.schemas.reporting import SavedReportIn
from app.services.report_delivery import ReportDeliveryError
from app.services.saved_reports import validate_saved_parameters


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first = Organization(name="Saved Reports One", slug="saved-reports-one")
    second = Organization(name="Saved Reports Two", slug="saved-reports-two")
    db.add_all([first, second])
    db.flush()
    users = []
    for index, org in enumerate((first, second, first)):
        row = User(
            email=f"saved-report-{index}@example.com", hashed_password="x",
            first_name="Report", last_name=str(index), role=UserRole.ADMIN,
            organization_id=org.id, is_active=True,
        )
        db.add(row)
        users.append(row)
    db.commit()
    return users


def test_parameter_whitelist_and_required_values():
    assert validate_saved_parameters("accounting.trial_balance", {"as_of": "2026-01-02", "include_zero": "true"}) == {
        "as_of": "2026-01-02", "include_zero": True,
    }
    for key, params in (
        ("tenant.directory", {}),
        ("accounting.chart_of_accounts", {"sql": "SELECT * FROM users"}),
        ("accounting.general_ledger", {}),
        ("owner.statement", {"statement_id": -5}),
        ("accounting.general_ledger", {"account_id": 1, "date_from": "2026-03-01", "date_to": "2026-02-01"}),
    ):
        with pytest.raises(ReportDeliveryError):
            validate_saved_parameters(key, params)


def test_saved_reports_are_private_cross_org_and_audited(monkeypatch):
    db, engine = _session()
    try:
        first, second, colleague = _seed(db)
        monkeypatch.setattr(reporting, "permission_allows_user", lambda *a, **k: True)
        payload = SavedReportIn(name="  Month end  ", report_key="accounting.trial_balance", parameters={"include_zero": False})
        created = reporting.create_saved_report(payload, db=db, current_user=first)
        assert created.name == "Month end"
        assert created.parameters == {"include_zero": False}
        assert reporting.list_saved_reports(db=db, current_user=first).total == 1
        assert reporting.list_saved_reports(db=db, current_user=second).total == 0
        assert reporting.list_saved_reports(db=db, current_user=colleague).total == 0
        for user in (second, colleague):
            with pytest.raises(HTTPException) as exc:
                reporting.get_saved_report(created.id, db=db, current_user=user)
            assert exc.value.status_code == 404
            with pytest.raises(HTTPException) as exc:
                reporting.delete_saved_report(created.id, db=db, current_user=user)
            assert exc.value.status_code == 404
        updated = reporting.update_saved_report(
            created.id,
            SavedReportIn(name="Updated", report_key="accounting.chart_of_accounts", parameters={}),
            db=db, current_user=first,
        )
        assert updated.name == "Updated"
        assert db.query(SavedReport).filter_by(organization_id=first.organization_id, user_id=first.id).count() == 1
        reporting.delete_saved_report(created.id, db=db, current_user=first)
        assert reporting.list_saved_reports(db=db, current_user=first).total == 0
    finally:
        db.close()
        engine.dispose()


def test_saved_report_requires_report_permission_and_rechecks_on_read(monkeypatch):
    db, engine = _session()
    try:
        first, _, _ = _seed(db)
        monkeypatch.setattr(reporting, "permission_allows_user", lambda *a, **k: True)
        created = reporting.create_saved_report(
            SavedReportIn(name="Private", report_key="accounting.trial_balance", parameters={}),
            db=db, current_user=first,
        )
        monkeypatch.setattr(
            reporting, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL",
        )
        assert reporting.list_saved_reports(db=db, current_user=first).total == 0
        with pytest.raises(HTTPException) as exc:
            reporting.get_saved_report(created.id, db=db, current_user=first)
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            reporting.create_saved_report(
                SavedReportIn(name="Forbidden", report_key="accounting.trial_balance", parameters={}),
                db=db, current_user=first,
            )
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            reporting.export_report_csv("accounting.trial_balance", SimpleNamespace(query_params={}), db=db, current_user=first)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
