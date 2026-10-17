"""Named property groups: real membership, hybrid gating, org/assignment isolation."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.property import Property, PropertyAssignment
from app.models.property_group import PropertyGroup, PropertyGroupMembership
from app.models.user import Organization, User, UserRole
from app.routers import property_groups as group_router
from app.routers import reporting as reporting_router
from app.schemas.property_group import PropertyGroupUpsertIn
from app.services import property_groups
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import (
    ReportDeliveryError, build_report_payload, report_csv_bytes,
)

KEY = "property.group_directory"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first = Organization(name="Groups One", slug="groups-one")
    second = Organization(name="Groups Two", slug="groups-two")
    db.add_all([first, second]); db.flush()
    def user(o, role, name):
        row = User(
            organization_id=o.id, role=role, first_name=name,
            last_name="Group", email=f"{name.lower()}@groups.example",
            hashed_password="x", is_active=True,
        )
        db.add(row); db.flush()
        return row
    admin = user(first, UserRole.ADMIN, "Admin")
    manager = user(first, UserRole.MANAGER, "Manager")
    tenant = user(first, UserRole.TENANT, "Tenant")
    foreign = user(second, UserRole.ADMIN, "Foreign")
    def prop(o, name):
        row = Property(
            organization_id=o.id, name=name,
            address_line1="=1 Group Street", city="Cleveland",
            state="OH", zip_code="44113", is_active=True,
        )
        db.add(row); db.flush()
        return row
    visible = prop(first, "=Visible")
    hidden = prop(first, "Unassigned")
    outsider = prop(second, "Foreign Property")
    db.add(PropertyAssignment(
        property_id=visible.id, user_id=manager.id,
        role=UserRole.MANAGER, is_active=True,
    ))
    db.commit()
    return admin, manager, tenant, foreign, visible, hidden, outsider


def _allow(monkeypatch):
    monkeypatch.setattr(property_groups, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(property_groups, "resolve_customer_features",
                        lambda *a, **kw: [SimpleNamespace(
                            key=property_groups.GROUP_FEATURE, allowed=True,
                        )])


def _payload(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, report_key=KEY,
        parameters=params, current_user=actor,
    )


def test_explicit_group_membership_crud_is_scoped_and_audited(monkeypatch):
    db, engine = _session()
    try:
        _allow(monkeypatch)
        admin, manager, tenant, foreign, visible, hidden, outsider = _seed(db)
        initial = group_router.create_group(
            PropertyGroupUpsertIn(name="  =North  ", description="=Named",
                                  property_ids=[visible.id, hidden.id]),
            Response(), db=db, current_user=admin,
        )
        assert initial.name == "=North" and initial.property_ids == [visible.id, hidden.id]
        assert db.query(PropertyGroup).count() == 1
        assert db.query(PropertyGroupMembership).count() == 2
        with pytest.raises(HTTPException) as exc:
            group_router.create_group(
                PropertyGroupUpsertIn(name="=NORTH", property_ids=[]),
                Response(), db=db, current_user=admin,
            )
        assert exc.value.status_code == 422
        with pytest.raises(HTTPException) as exc:
            group_router.create_group(
                PropertyGroupUpsertIn(name="Another", property_ids=[outsider.id]),
                Response(), db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
        managed = group_router.get_groups(Response(), db=db, current_user=manager)
        assert len(managed) == 1 and managed[0].property_ids == [visible.id]
        assert group_router.get_groups(Response(), db=db, current_user=foreign) == []
        with pytest.raises(HTTPException) as exc:
            group_router.create_group(
                PropertyGroupUpsertIn(name="Bad", property_ids=[]),
                Response(), db=db, current_user=manager,
            )
        assert exc.value.status_code == 403
        replaced = group_router.update_group(
            initial.id, PropertyGroupUpsertIn(name="New Name", property_ids=[visible.id]),
            Response(), db=db, current_user=admin,
        )
        assert replaced.name == "New Name" and replaced.property_ids == [visible.id]
        assert db.query(PropertyGroupMembership).count() == 1
        group_router.remove_group(initial.id, db=db, current_user=admin)
        assert db.query(PropertyGroup).count() == 0
        assert db.query(PropertyGroupMembership).count() == 0
        assert db.query(AuditLog).filter(AuditLog.entity_type == "property_group").count() >= 3
    finally:
        db.close(); engine.dispose()


def test_group_report_manager_no_name_leak_and_csv_escape(monkeypatch):
    db, engine = _session()
    try:
        _allow(monkeypatch)
        admin, manager, _, foreign, visible, hidden, outsider = _seed(db)
        both = property_groups.save_group(
            db, actor=admin,
            payload=PropertyGroupUpsertIn(
                name="=Combined", description="=Marketing",
                property_ids=[visible.id, hidden.id],
            ),
        )
        secret = property_groups.save_group(
            db, actor=admin,
            payload=PropertyGroupUpsertIn(name="Secret", property_ids=[hidden.id]),
        )
        output = _payload(db, manager)
        assert len(output.rows) == 1 and output.rows[0][-1] == visible.id
        assert "Secret" not in report_csv_bytes(output).decode("utf-8-sig")
        assert "Unassigned" not in report_csv_bytes(output).decode("utf-8-sig")
        admin_csv = report_csv_bytes(_payload(db, admin)).decode("utf-8-sig")
        assert "'=Combined" in admin_csv and "'=Marketing" in admin_csv
        assert "'=Visible" in admin_csv and "'=1 Group Street" in admin_csv
        assert len(_payload(db, admin).rows) == 3
        with pytest.raises(ReportDeliveryError, match="not found"):
            _payload(db, manager, group_id=secret.id)
        with pytest.raises(ReportDeliveryError):
            _payload(db, foreign, group_id=both.id)
        with pytest.raises(ReportDeliveryError):
            _payload(db, admin, group_id=9999)
    finally:
        db.close(); engine.dispose()


def test_hybrid_feature_gate_and_role_permissions_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        _allow(monkeypatch)
        admin, manager, tenant, *_ = _seed(db)
        saved = property_groups.save_group(
            db, actor=admin, payload=PropertyGroupUpsertIn(name="Open", property_ids=[]),
        )
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, tenant)
        monkeypatch.setattr(property_groups, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=property_groups.GROUP_FEATURE, allowed=False,
                            )])
        with pytest.raises(ReportDeliveryError, match="not enabled"):
            _payload(db, admin)
        with pytest.raises(ReportDeliveryError, match="not enabled"):
            property_groups.list_groups(db, actor=admin)
        monkeypatch.setattr(property_groups, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=property_groups.GROUP_FEATURE, allowed=True,
                            )])
        monkeypatch.setattr(property_groups, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "PROPERTIES.GROUPS")
        with pytest.raises(ReportDeliveryError, match="permission"):
            _payload(db, admin)
        with pytest.raises(ReportDeliveryError, match="permission"):
            property_groups.delete_group(db, actor=admin, group_id=saved.id)
        assert db.query(PropertyGroup).count() == 1
    finally:
        db.close(); engine.dispose()


def test_catalog_preview_csv_email_and_export_revocation(monkeypatch):
    db, engine = _session()
    try:
        _allow(monkeypatch)
        admin, manager, tenant, foreign, visible, hidden, outsider = _seed(db)
        property_groups.save_group(
            db, actor=admin,
            payload=PropertyGroupUpsertIn(name="=One", property_ids=[visible.id]),
        )
        item = next(item for item in REPORT_CATALOG if item.key == KEY)
        assert item.tier == "STANDARD" and item.href == "/dashboard/reporting/property-groups"
        assert reporting_router.REPORT_PERMISSIONS[KEY] == "PROPERTIES.GROUPS"
        monkeypatch.setattr(reporting_router, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=True,
                            )])
        req = SimpleNamespace(query_params={})
        response = Response()
        result = reporting_router.preview_property_group_directory(
            req, response, db=db, current_user=admin,
        )
        assert result["total"] == 1 and response.headers["cache-control"] == "no-store"
        csv = reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert b"Property ID" in csv.body
        sent = {}
        monkeypatch.setattr(reporting_router, "send_email", lambda **kw: sent.update(kw))
        result = reporting_router.email_report(
            KEY, reporting_router.ReportEmailIn(
                recipient="admin@example.com", parameters={},
            ), db=db, current_user=admin,
        )
        assert result.sent and b"Group ID" in sent["attachments"][0][1]
        monkeypatch.setattr(reporting_router, "resolve_customer_features",
                            lambda *a, **kw: [SimpleNamespace(
                                key=reporting_router.EXPORT_FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as exc:
            reporting_router.preview_property_group_directory(
                req, Response(), db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
        monkeypatch.setattr(reporting_router, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            reporting_router.export_report_csv(KEY, req, db=db, current_user=admin)
        assert exc.value.status_code == 403
        with pytest.raises(ReportDeliveryError):
            _payload(db, admin, extra="not allowed")
    finally:
        db.close(); engine.dispose()
