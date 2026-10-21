"""Phase 3.7 inspections: explicit staff facts and strict tenant/org scope."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, PropertyAssignment, Unit
from app.models.unit_inspection import UnitInspectionRecord
from app.models.user import Organization, User, UserRole
from app.routers import reporting as report_router
from app.routers import unit_inspections as inspection_router
from app.schemas.unit_inspection import UnitInspectionCreateIn
from app.services import unit_inspections
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes

KEY = "property.unit_inspection"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    one = Organization(name="Inspection One", slug="inspection-one")
    other = Organization(name="Inspection Other", slug="inspection-other")
    db.add_all([one, other]); db.flush()
    def user(org, role, name):
        row = User(organization_id=org.id, role=role, first_name=name,
                   last_name="Inspection", email=f"{name.lower()}@inspection.example",
                   hashed_password="x", is_active=True)
        db.add(row); db.flush()
        return row
    admin = user(one, UserRole.ADMIN, "Admin")
    manager = user(one, UserRole.MANAGER, "Manager")
    tenant = user(one, UserRole.TENANT, "Tenant")
    foreign_admin = user(other, UserRole.ADMIN, "Foreign")
    def prop(org, name):
        row = Property(organization_id=org.id, name=name,
                       address_line1="1 Inspected Lane", city="Cleveland",
                       state="OH", zip_code="44113", is_active=True)
        db.add(row); db.flush()
        return row
    first = prop(one, "=Visible")
    hidden = prop(one, "Unassigned")
    foreign_prop = prop(other, "Secret")
    db.add(PropertyAssignment(
        property_id=first.id, user_id=manager.id,
        role=UserRole.MANAGER, is_active=True,
    ))
    def unit(prop_, name):
        row = Unit(property_id=prop_.id, unit_number=name, is_active=True)
        db.add(row); db.flush()
        return row
    first_unit = unit(first, "=A")
    hidden_unit = unit(hidden, "B")
    foreign_unit = unit(foreign_prop, "C")
    db.commit()
    return admin, manager, tenant, foreign_admin, first, hidden, foreign_prop, first_unit, hidden_unit, foreign_unit


def _payload(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id,
        report_key=KEY, parameters=params, current_user=actor,
    )


def _input(unit, condition="ATTENTION_NEEDED", findings="=Needs repair"):
    return UnitInspectionCreateIn(
        unit_id=unit.id, inspection_date=date.today(),
        recorded_condition=condition, findings=findings,
    )


def test_inspection_only_explicit_rows_audited_no_gl_writes(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other, first, hidden, foreign, first_unit, hidden_unit, foreign_unit = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        assert _payload(db, admin).rows == ()
        before = db.query(GLTransaction).count()
        saved = inspection_router.create_inspection(
            _input(first_unit), Response(), db=db, current_user=admin,
        )
        assert saved.recorded_condition == "ATTENTION_NEEDED"
        assert saved.inspection_date == date.today()
        assert saved.recorded_by_id == admin.id
        assert saved.recorded_by_name == "Admin Inspection"
        assert saved.property_name == "=Visible"
        assert saved.unit_number == "=A"
        assert db.query(UnitInspectionRecord).count() == 1
        assert db.query(AuditLog).filter_by(entity_type="unit_inspection_record").count() == 1
        assert db.query(GLTransaction).count() == before
        rows = _payload(db, admin).rows
        assert len(rows) == 1
        assert rows[0][:5] == ("=Visible", "=A", date.today(), "ATTENTION_NEEDED", "=Needs repair")
        assert rows[0][-1] == first_unit.id
        assert "'=Needs repair" in report_csv_bytes(_payload(db, admin)).decode("utf-8-sig")
        assert "'=Visible" in report_csv_bytes(_payload(db, admin)).decode("utf-8-sig")
        assert inspection_router.get_inspections(Response(), property_id=None, unit_id=None, db=db, current_user=manager)[0].id == saved.id
    finally:
        db.close(); engine.dispose()


def test_inspection_parent_binding_and_full_findings_are_audited(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, foreign_admin, first, hidden, foreign, first_unit, hidden_unit, foreign_unit = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        saved = inspection_router.create_inspection(
            _input(first_unit, findings="Observed actual water damage"),
            Response(), db=db, current_user=admin,
        )
        import json
        audit = db.query(AuditLog).filter_by(
            entity_type="unit_inspection_record", entity_id=saved.id, action="created",
        ).one()
        assert json.loads(audit.new_value)["findings"] == "Observed actual water damage"

        # Simulate a corrupted parent pointer: the persisted organization is
        # correct but the claimed property does not match the actual unit.
        row = db.query(UnitInspectionRecord).filter_by(id=saved.id).one()
        row.property_id = hidden.id
        db.commit()
        assert inspection_router.get_inspections(
            Response(), property_id=None, unit_id=None,
            db=db, current_user=admin,
        ) == []
        assert _payload(db, admin).rows == ()

        # Reinstating the real unit's property recovers historical evidence.
        row.property_id = first.id
        db.commit()
        assert [item.id for item in inspection_router.get_inspections(
            Response(), property_id=None, unit_id=None,
            db=db, current_user=admin,
        )] == [saved.id]
        assert len(_payload(db, admin).rows) == 1
        assert db.query(AuditLog).filter_by(
            entity_type="unit_inspection_record", entity_id=saved.id,
        ).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_inspection_detail_honors_scope_and_retired_history(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, outside, prop, hidden, foreign, unit, other_unit, foreign_unit = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        saved = inspection_router.create_inspection(
            _input(unit, findings="Checked shutoff valves"),
            Response(), db=db, current_user=admin,
        )
        detail = inspection_router.get_inspection_detail(saved.id, Response(), db=db, current_user=manager)
        assert detail.id == saved.id
        assert detail.findings == "Checked shutoff valves"
        for denied in (tenant, outside):
            with pytest.raises(HTTPException) as exc:
                inspection_router.get_inspection_detail(saved.id, Response(), db=db, current_user=denied)
            assert exc.value.status_code in {403, 404}
        with pytest.raises(HTTPException) as exc:
            inspection_router.get_inspection_detail(saved.id + 10000, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404

        # Retiring property inventory does not erase authorized history.
        prop.is_active = False
        prop.deleted_at = datetime.utcnow()
        db.commit()
        assert inspection_router.get_inspection_detail(
            saved.id, Response(), db=db, current_user=admin,
        ).id == saved.id

        # A stale/revoked manager assignment cannot retrieve detail.
        assignment = db.query(PropertyAssignment).filter_by(
            user_id=manager.id, property_id=prop.id,
        ).one()
        assignment.deleted_at = datetime.utcnow()
        db.commit()
        with pytest.raises(HTTPException) as exc:
            inspection_router.get_inspection_detail(saved.id, Response(), db=db, current_user=manager)
        assert exc.value.status_code == 404
    finally:
        db.close()
        engine.dispose()


def test_inspection_history_filters_preserve_scope_and_chronology(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, foreign_admin, prop, hidden, foreign, unit, hidden_unit, foreign_unit = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        older = inspection_router.create_inspection(
            UnitInspectionCreateIn(
                unit_id=unit.id, inspection_date=date.today() - timedelta(days=2),
                recorded_condition="SATISFACTORY", findings="Prior safety check",
            ), Response(), db=db, current_user=admin,
        )
        recent = inspection_router.create_inspection(
            UnitInspectionCreateIn(
                unit_id=unit.id, inspection_date=date.today(),
                recorded_condition="ATTENTION_NEEDED", findings="Urgent followup",
            ), Response(), db=db, current_user=admin,
        )
        def history(user, **filters):
            return inspection_router.get_inspections(
                Response(), property_id=None, unit_id=None,
                db=db, current_user=user, **filters,
            )
        assert [x.id for x in history(admin)] == [recent.id, older.id]
        assert [x.id for x in history(admin, limit=1)] == [recent.id]
        assert [x.id for x in history(admin, limit=1, offset=1)] == [older.id]
        assert [x.id for x in history(admin, recorded_condition="ATTENTION_NEEDED", limit=1)] == [recent.id]
        assert [x.id for x in history(manager, recorded_condition="SATISFACTORY")] == [older.id]
        assert [x.id for x in history(admin, date_from=date.today())] == [recent.id]
        assert [x.id for x in history(admin, date_to=date.today() - timedelta(days=1))] == [older.id]
        with pytest.raises(HTTPException) as invalid:
            history(admin, date_from=date.today(), date_to=date.today() - timedelta(days=1))
        assert invalid.value.status_code == 422
        with pytest.raises(HTTPException):
            inspection_router.get_inspections(Response(), property_id=prop.id, unit_id=None, db=db, current_user=foreign_admin)
        with pytest.raises(HTTPException) as forbidden:
            history(tenant)
        assert forbidden.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_unit_filtered_inspection_history_respects_assignment_and_organization(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, foreign_admin, first, hidden, foreign, unit, hidden_unit, foreign_unit = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        visible = inspection_router.create_inspection(_input(unit), Response(), db=db, current_user=admin)
        other = inspection_router.create_inspection(_input(hidden_unit), Response(), db=db, current_user=admin)
        def history(actor, unit_id):
            return inspection_router.get_inspections(
                Response(), property_id=None, unit_id=unit_id, limit=100, offset=0,
                db=db, current_user=actor,
            )
        assert [row.id for row in history(admin, unit.id)] == [visible.id]
        assert [row.id for row in history(admin, hidden_unit.id)] == [other.id]
        assert [row.id for row in history(manager, unit.id)] == [visible.id]
        for actor, target in (
            (manager, hidden_unit.id), (admin, foreign_unit.id),
            (foreign_admin, unit.id),
        ):
            with pytest.raises(HTTPException) as exc:
                history(actor, target)
            assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as forbidden:
            history(tenant, unit.id)
        assert forbidden.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_inspection_recorder_name_never_leaks_foreign_organization(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, outside, prop, hidden, foreign, unit, hidden_unit, foreign_unit = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        saved = inspection_router.create_inspection(_input(unit), Response(), db=db, current_user=admin)
        assert saved.recorded_by_name == "Admin Inspection"
        assert inspection_router.get_inspection_detail(
            saved.id, Response(), db=db, current_user=manager,
        ).recorded_by_name == "Admin Inspection"
        row = db.query(UnitInspectionRecord).filter_by(id=saved.id).one()
        row.recorded_by_id = outside.id
        db.commit()
        detail = inspection_router.get_inspection_detail(
            saved.id, Response(), db=db, current_user=admin,
        )
        assert detail.recorded_by_id == outside.id
        assert detail.recorded_by_name is None
        history = inspection_router.get_inspections(
            Response(), property_id=None, unit_id=None, db=db, current_user=admin,
        )
        assert history[0].recorded_by_name is None
        assert all("Foreign Inspection" != (item.recorded_by_name or "") for item in history)
    finally:
        db.close()
        engine.dispose()


def test_scope_foreign_unit_assignment_role_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other, first, hidden, foreign, first_unit, hidden_unit, foreign_unit = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        inspection_router.create_inspection(_input(first_unit), Response(), db=db, current_user=admin)
        for target in (hidden_unit, foreign_unit):
            with pytest.raises(HTTPException) as exc:
                inspection_router.create_inspection(
                    _input(target), Response(), db=db, current_user=manager,
                )
            assert exc.value.status_code == 404
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, tenant, property_id=first.id)
        with pytest.raises(ReportDeliveryError, match="Property not found"):
            _payload(db, other, property_id=first.id)
        with pytest.raises(ReportDeliveryError, match="Property not found"):
            _payload(db, manager, property_id=hidden.id)
        with pytest.raises(ReportDeliveryError, match="Unit not found"):
            _payload(db, manager, unit_id=foreign_unit.id)
        with pytest.raises(ReportDeliveryError):
            _payload(db, admin, sql="select")
        with pytest.raises(ReportDeliveryError):
            _payload(db, admin, date_from="2026-12-01", date_to="2026-01-01")
        monkeypatch.setattr(unit_inspections, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "PROPERTIES.UNITS")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, manager)
        with pytest.raises(HTTPException) as exc:
            inspection_router.create_inspection(
                _input(first_unit), Response(), db=db, current_user=manager,
            )
        assert exc.value.status_code == 403
        assert db.query(UnitInspectionRecord).count() == 1
    finally:
        db.close(); engine.dispose()


def test_dates_and_inactive_unit_rejected(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, *_ = _seed(db)
        unit = db.query(Unit).first()
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        with pytest.raises(ValueError):
            UnitInspectionCreateIn(
                unit_id=unit.id, inspection_date=date.today() + timedelta(days=1),
                recorded_condition="SATISFACTORY",
            )
        with pytest.raises(ValueError):
            UnitInspectionCreateIn(
                unit_id=unit.id, inspection_date=date.today(),
                recorded_condition="BAD",
            )
        unit.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as exc:
            inspection_router.create_inspection(_input(unit), Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_and_export_revocation(monkeypatch):
    db, engine = _session()
    try:
        admin, _, _, _, first, _, _, unit, _, _ = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        inspection_router.create_inspection(_input(unit), Response(), db=db, current_user=admin)
        item = next(x for x in REPORT_CATALOG if x.key == KEY)
        assert item.presentation == "BUTTON"
        assert item.href == "/dashboard/reporting/unit-inspections"
        assert report_router.REPORT_PERMISSIONS[KEY] == "PROPERTIES.UNITS"
        monkeypatch.setattr(report_router, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        req = SimpleNamespace(query_params={"property_id": str(first.id)})
        resp = Response()
        preview = report_router.preview_unit_inspections(req, resp, db=db, current_user=admin)
        assert preview["total"] == 1
        assert resp.headers["cache-control"] == "no-store"
        csv = report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"staff-recorded" in csv.body
        sent = {}
        monkeypatch.setattr(report_router, "send_email", lambda **kw: sent.update(kw))
        result = report_router.email_report(
            KEY, report_router.ReportEmailIn(
                recipient="admin@example.com", parameters={"property_id": first.id},
            ), db=db, current_user=admin,
        )
        assert result.sent and b"Needs repair" in sent["attachments"][0][1]
        monkeypatch.setattr(report_router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=report_router.EXPORT_FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as exc:
            report_router.preview_unit_inspections(req, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(report_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            report_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()


def test_archived_inventory_retains_audited_inspection_history_without_new_writes(monkeypatch):
    """Archived unit/property evidence remains visible only to authorized staff."""
    db, engine = _session()
    try:
        admin, manager, tenant, foreign_admin, first, hidden, foreign, unit, _, _ = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        saved = inspection_router.create_inspection(
            _input(unit), Response(), db=db, current_user=admin,
        )
        audit_count = db.query(AuditLog).filter_by(entity_type="unit_inspection_record").count()

        # Deactivation and later soft deletion must not erase historical evidence.
        unit.is_active = False
        first.is_active = False
        db.commit()
        for status in ("inactive", "soft-deleted"):
            if status == "soft-deleted":
                unit.deleted_at = datetime.utcnow()
                first.deleted_at = datetime.utcnow()
                db.commit()
            for actor in (admin, manager):
                history = inspection_router.get_inspections(
                    Response(), property_id=first.id, unit_id=unit.id,
                    db=db, current_user=actor,
                )
                assert [item.id for item in history] == [saved.id]
                assert history[0].property_name == "=Visible"
                assert history[0].unit_number == "=A"
                assert [row[-2:] for row in _payload(
                    db, actor, property_id=first.id, unit_id=unit.id,
                ).rows] == [(first.id, unit.id)]
                with pytest.raises(HTTPException) as exc:
                    inspection_router.create_inspection(
                        _input(unit), Response(), db=db, current_user=actor,
                    )
                assert exc.value.status_code == 404

        # Organization separation, tenancy restrictions, and assignment
        # revocation still apply even to archived evidence.
        with pytest.raises(HTTPException) as exc:
            inspection_router.get_inspections(
                Response(), property_id=first.id, unit_id=unit.id,
                db=db, current_user=foreign_admin,
            )
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            inspection_router.get_inspections(
                Response(), property_id=None, unit_id=None,
                db=db, current_user=tenant,
            )
        assert exc.value.status_code == 403
        assignment = db.query(PropertyAssignment).filter_by(
            property_id=first.id, user_id=manager.id,
        ).one()
        assignment.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as exc:
            inspection_router.get_inspections(
                Response(), property_id=first.id, unit_id=unit.id,
                db=db, current_user=manager,
            )
        assert exc.value.status_code == 404

        assert db.query(UnitInspectionRecord).count() == 1
        assert db.query(AuditLog).filter_by(
            entity_type="unit_inspection_record",
        ).count() == audit_count
    finally:
        db.close()
        engine.dispose()


def test_inspection_history_pages_are_scoped_ordered_and_do_not_truncate_reports(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, other, first, hidden, foreign, unit, _, _ = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        saved = []
        for index in range(3):
            item = UnitInspectionCreateIn(
                unit_id=unit.id,
                inspection_date=date.today() - timedelta(days=index),
                recorded_condition="SATISFACTORY",
                findings=f"Snapshot {index}",
            )
            saved.append(inspection_router.create_inspection(
                item, Response(), db=db, current_user=admin,
            ).id)

        def page(actor, limit, offset):
            return inspection_router.get_inspections(
                Response(), property_id=first.id, unit_id=unit.id,
                limit=limit, offset=offset, db=db, current_user=actor,
            )

        assert [row.id for row in page(admin, 2, 0)] == saved[:2]
        assert [row.id for row in page(admin, 2, 2)] == saved[2:]
        assert page(admin, 2, 3) == []
        assert [row.id for row in page(manager, 1, 1)] == [saved[1]]
        # Unpaged report and direct historical API preserve all three facts.
        assert len(_payload(db, admin, property_id=first.id).rows) == 3
        assert len(inspection_router.get_inspections(
            Response(), property_id=first.id, unit_id=unit.id,
            db=db, current_user=admin,
        )) == 3
        with pytest.raises(HTTPException) as denied:
            page(other, 1, 0)
        assert denied.value.status_code == 404
        with pytest.raises(HTTPException) as denied:
            page(tenant, 1, 0)
        assert denied.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_inspection_checklist_persists_scoped_evidence_and_prevents_duplicates(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, tenant, outside, prop, _, _, unit, _, _ = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **k: True)
        submitted = UnitInspectionCreateIn(
            unit_id=unit.id, inspection_date=date.today(),
            recorded_condition="ATTENTION_NEEDED", findings="Alarm needs replacement.",
            checklist_items=[
                {"area": "SAFETY", "condition": "ATTENTION_NEEDED", "notes": "Replace alarm"},
                {"area": "PLUMBING", "condition": "SATISFACTORY", "notes": ""},
            ],
        )
        recorded = inspection_router.create_inspection(
            submitted, Response(), db=db, current_user=admin,
        )
        assert [item.area for item in recorded.checklist_items] == ["SAFETY", "PLUMBING"]
        stored = db.query(UnitInspectionRecord).filter_by(id=recorded.id).one()
        assert '"SAFETY"' in stored.checklist_json
        rows = inspection_router.get_inspections(
            Response(), property_id=prop.id, unit_id=unit.id,
            db=db, current_user=manager,
        )
        assert rows[0].checklist_items[0].notes == "Replace alarm"
        assert '"SAFETY"' in str(_payload(db, admin, unit_id=unit.id).rows[0])
        audit = db.query(AuditLog).filter_by(
            entity_type="unit_inspection_record", entity_id=recorded.id,
        ).one()
        assert '"SAFETY"' in audit.new_value
        with pytest.raises(ValueError, match="duplicated"):
            UnitInspectionCreateIn(
                unit_id=unit.id, inspection_date=date.today(),
                recorded_condition="NOT_ASSESSED",
                checklist_items=[
                    {"area": "SAFETY", "condition": "SATISFACTORY"},
                    {"area": "SAFETY", "condition": "ATTENTION_NEEDED"},
                ],
            )
        with pytest.raises(HTTPException) as denied:
            inspection_router.create_inspection(
                submitted, Response(), db=db, current_user=tenant,
            )
        assert denied.value.status_code == 403
        assert db.query(UnitInspectionRecord).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_inspection_evidence_and_reports_require_true_property_manager_role(monkeypatch):
    """Global MANAGER + CREW property membership is never inspection authority."""
    db, engine = _session()
    try:
        admin, manager, tenant, foreign_admin, prop, hidden, foreign, unit, hidden_unit, foreign_unit = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **kw: True)
        inspection = inspection_router.create_inspection(
            _input(unit, findings="Observed fixture leak"),
            Response(), db=db, current_user=admin,
        )
        membership = db.query(PropertyAssignment).filter_by(
            user_id=manager.id, property_id=prop.id,
        ).one()
        assert membership.role == UserRole.MANAGER
        assert inspection_router.get_inspection_detail(
            inspection.id, Response(), db=db, current_user=manager,
        ).id == inspection.id

        # Reassignment to CREW does not change the global MANAGER role,
        # and cannot grant read, create, detail, work-order links, or exports.
        membership.role = UserRole.CREW
        db.commit()
        assert inspection_router.get_inspections(
            Response(), property_id=None, unit_id=None,
            limit=None, offset=0, recorded_condition=None,
            date_from=None, date_to=None,
            db=db, current_user=manager,
        ) == []
        for attempt in (
            lambda: inspection_router.get_inspection_detail(
                inspection.id, Response(), db=db, current_user=manager,
            ),
            lambda: inspection_router.get_inspection_work_orders(
                inspection.id, Response(), db=db, current_user=manager,
            ),
            lambda: inspection_router.create_inspection(
                _input(unit, findings="Unauthorized record"),
                Response(), db=db, current_user=manager,
            ),
        ):
            with pytest.raises(HTTPException) as denied:
                attempt()
            assert denied.value.status_code == 404
        with pytest.raises(ReportDeliveryError, match="Property not found"):
            _payload(db, manager, property_id=prop.id)
        assert db.query(UnitInspectionRecord).count() == 1
        assert db.query(AuditLog).filter_by(
            entity_type="unit_inspection_record", action="created",
        ).count() == 1

        # A restored active MANAGER property assignment restores access.
        membership.role = UserRole.MANAGER
        db.commit()
        assert inspection_router.get_inspection_detail(
            inspection.id, Response(), db=db, current_user=manager,
        ).id == inspection.id
    finally:
        db.close()
        engine.dispose()


def test_independent_inspection_review_is_scoped_immutable_idempotent_and_audited(monkeypatch):
    from sqlalchemy import text
    from sqlalchemy.exc import DatabaseError
    from app.models.unit_inspection import UnitInspectionReview
    from app.schemas.unit_inspection import InspectionReviewIn

    db, engine = _session()
    try:
        admin, manager, tenant, outsider, prop, hidden, foreign_prop, unit, hidden_unit, foreign_unit = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **kw: True)
        saved = inspection_router.create_inspection(
            _input(unit, findings="Leaking exterior faucet"), Response(),
            db=db, current_user=admin,
        )
        decision = InspectionReviewIn(
            decision="FOLLOW_UP_REQUIRED",
            notes="Plumbing follow-up must be scheduled separately",
        )
        assert inspection_router.read_inspection_review(
            saved.id, Response(), db=db, current_user=manager,
        ) is None
        for forbidden in (admin, tenant, outsider):
            with pytest.raises(HTTPException) as denied:
                inspection_router.review_inspection(
                    saved.id, decision, Response(), db=db, current_user=forbidden,
                )
            assert denied.value.status_code in (403, 404)
        assert db.query(UnitInspectionReview).count() == 0

        recorded = inspection_router.review_inspection(
            saved.id, decision, Response(), db=db, current_user=manager,
        )
        assert recorded.inspection_id == saved.id
        assert recorded.reviewer_id == manager.id
        assert recorded.decision == "FOLLOW_UP_REQUIRED"
        assert recorded.notes == decision.notes
        assert inspection_router.read_inspection_review(
            saved.id, Response(), db=db, current_user=admin,
        ).id == recorded.id
        original = inspection_router.get_inspection_detail(
            saved.id, Response(), db=db, current_user=admin,
        )
        assert original.findings == "Leaking exterior faucet"
        assert original.recorded_by_id == admin.id
        assert db.query(AuditLog).filter_by(
            entity_type="unit_inspection_review",
            entity_id=recorded.id,
            action="independent_review_recorded",
        ).count() == 1
        replay = inspection_router.review_inspection(
            saved.id, decision, Response(), db=db, current_user=manager,
        )
        assert replay.id == recorded.id
        for actor, conflicting in (
            (manager, InspectionReviewIn(decision="CONFIRMED", notes="Different decision not permitted")),
            (admin, decision),
        ):
            with pytest.raises(HTTPException):
                inspection_router.review_inspection(
                    saved.id, conflicting, Response(), db=db, current_user=actor,
                )
        assert db.query(UnitInspectionReview).count() == 1
        assert db.query(AuditLog).filter_by(
            entity_type="unit_inspection_review", entity_id=recorded.id,
        ).count() == 1

        # A manager whose property role changes to CREW cannot see a prior review.
        assignment = db.query(PropertyAssignment).filter_by(
            property_id=prop.id, user_id=manager.id,
        ).one()
        assignment.role = UserRole.CREW
        db.commit()
        with pytest.raises(HTTPException) as denied:
            inspection_router.read_inspection_review(
                saved.id, Response(), db=db, current_user=manager,
            )
        assert denied.value.status_code == 404

        # Database triggers protect historical decisions even outside the ORM.
        with pytest.raises(DatabaseError):
            db.execute(text(
                "UPDATE unit_inspection_reviews SET decision='CONFIRMED' WHERE id=:id"
            ), {"id": recorded.id})
            db.commit()
        db.rollback()
        assert db.query(UnitInspectionReview).one().decision == "FOLLOW_UP_REQUIRED"
        with pytest.raises(DatabaseError):
            db.execute(text("DELETE FROM unit_inspection_reviews WHERE id=:id"), {"id": recorded.id})
            db.commit()
        db.rollback()
        assert db.query(UnitInspectionReview).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_inspection_review_rejects_retired_inventory_and_missing_original_identity(monkeypatch):
    from app.schemas.unit_inspection import InspectionReviewIn
    from app.models.unit_inspection import UnitInspectionRecord, UnitInspectionReview

    db, engine = _session()
    try:
        admin, manager, _, _, prop, _, _, unit, _, _ = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **kw: True)
        saved = inspection_router.create_inspection(
            _input(unit), Response(), db=db, current_user=admin,
        )
        payload = InspectionReviewIn(decision="CONFIRMED", notes="Inspected supporting evidence")
        row = db.query(UnitInspectionRecord).filter_by(id=saved.id).one()
        row.recorded_by_id = None
        db.commit()
        with pytest.raises(HTTPException) as missing:
            inspection_router.review_inspection(
                saved.id, payload, Response(), db=db, current_user=manager,
            )
        assert missing.value.status_code == 409
        # Historical rows with an inspector from another organization are
        # not valid review origins, even when parent unit/property match.
        foreign_inspector = db.query(User).filter(
            User.organization_id != admin.organization_id,
        ).first()
        row.recorded_by_id = foreign_inspector.id
        db.commit()
        with pytest.raises(HTTPException) as foreign_origin:
            inspection_router.review_inspection(
                saved.id, payload, Response(), db=db, current_user=manager,
            )
        assert foreign_origin.value.status_code == 409
        row.recorded_by_id = admin.id
        prop.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as retired:
            inspection_router.review_inspection(
                saved.id, payload, Response(), db=db, current_user=manager,
            )
        assert retired.value.status_code == 409
        assert db.query(UnitInspectionReview).count() == 0
        assert db.query(AuditLog).filter_by(entity_type="unit_inspection_review").count() == 0
    finally:
        db.close()
        engine.dispose()

def test_organization_owner_can_independently_review_assigned_manager_inspection(monkeypatch):
    from app.schemas.unit_inspection import InspectionReviewIn
    from app.models.unit_inspection import UnitInspectionReview

    db, engine = _session()
    try:
        admin, manager, tenant, outsider, prop, hidden, foreign_prop, unit, hidden_unit, foreign_unit = _seed(db)
        monkeypatch.setattr(unit_inspections, "permission_allows_user", lambda *a, **kw: True)
        owner = User(
            organization_id=admin.organization_id, role=UserRole.OWNER,
            first_name="Property", last_name="Owner",
            email="review-owner@inspection.example",
            hashed_password="x", is_active=True,
        )
        db.add(owner)
        db.commit()
        captured = inspection_router.create_inspection(
            _input(unit, findings="Supervisor follow-up requested"),
            Response(), db=db, current_user=manager,
        )
        payload = InspectionReviewIn(
            decision="CONFIRMED", notes="The manager's observation matches the checklist.",
        )
        reviewed = inspection_router.review_inspection(
            captured.id, payload, Response(), db=db, current_user=owner,
        )
        assert reviewed.reviewer_id == owner.id
        assert reviewed.decision == "CONFIRMED"
        assert inspection_router.read_inspection_review(
            captured.id, Response(), db=db, current_user=admin,
        ).id == reviewed.id
        with pytest.raises(HTTPException) as self_review:
            inspection_router.review_inspection(
                captured.id, payload, Response(), db=db, current_user=manager,
            )
        assert self_review.value.status_code == 403
        assert db.query(UnitInspectionReview).count() == 1
    finally:
        db.close()
        engine.dispose()
