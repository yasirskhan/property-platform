"""Phase 4.8 staff commencement data must never become a commercial invoice."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.charge import Charge
from app.models.commercial_lease_abstract import CommercialLeaseAbstract
from app.models.entity_attachment import EntityAttachment
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease, LeaseStatus, RentInvoice
from app.models.property import Property, PropertyAssignment, PropertyType, Unit
from app.models.user import Organization, User, UserRole
from app.routers import affordable_programs, commercial_lease_abstracts as api
from app.routers import entity_attachments as attachments_api
from app.schemas.commercial_lease_abstract import CommercialLeaseAbstractIn, CommercialLeaseAbstractUpdate
from app.schemas.entity_attachment import EntityAttachmentShareUpdate
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def permissions(monkeypatch):
    monkeypatch.setattr(affordable_programs, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(affordable_programs, "resolve_customer_features",
                        lambda *a, **k: [SimpleNamespace(
                            key=affordable_programs.FEATURE_KEY, allowed=True,
                        )])
    monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **k: [
        SimpleNamespace(key=api.ATTACHMENTS_FEATURE_KEY, allowed=True),
    ])


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    a = Organization(name="Commercial Local", slug="commercial-local")
    b = Organization(name="Commercial Foreign", slug="commercial-foreign")
    db.add_all([a, b])
    db.flush()
    users = []
    for org, role, name in (
        (a, UserRole.ADMIN, "admin"), (a, UserRole.OWNER, "owner"),
        (a, UserRole.MANAGER, "manager"), (a, UserRole.TENANT, "tenant"),
        (b, UserRole.ADMIN, "foreign"), (b, UserRole.TENANT, "other-tenant"),
    ):
        row = User(organization_id=org.id, role=role, first_name=name,
                   last_name="Commercial", email=f"commercial-{name}@example.com",
                   hashed_password="x", is_active=True)
        db.add(row)
        users.append(row)
    db.flush()
    props = []
    for org, name, kind in (
        (a, "Assigned Commercial", PropertyType.COMMERCIAL),
        (a, "Unassigned Commercial", PropertyType.COMMERCIAL),
        (a, "Residential", PropertyType.MULTI_FAMILY),
        (b, "Foreign Commercial", PropertyType.COMMERCIAL),
    ):
        row = Property(organization_id=org.id, name=name,
                       property_type=kind, address_line1="20 Main",
                       city="Cleveland", state="OH", zip_code="44113",
                       is_active=True)
        db.add(row)
        props.append(row)
    db.flush()
    db.add(PropertyAssignment(
        property_id=props[0].id, user_id=users[2].id,
        role=UserRole.MANAGER, is_active=True,
    ))
    units = []
    leases = []
    for prop, tenant, label in (
        (props[0], users[3], "LOCAL-1"),
        (props[1], users[3], "OTHER-1"),
        (props[2], users[3], "HOME-1"),
        (props[3], users[5], "FOREIGN-1"),
    ):
        unit = Unit(property_id=prop.id, unit_number=label,
                    monthly_rent=Decimal("1200.00"), is_active=True)
        db.add(unit)
        db.flush()
        lease = Lease(
            unit_id=unit.id, tenant_id=tenant.id,
            start_date=date(2026, 1, 1), end_date=date(2027, 12, 31),
            monthly_rent=Decimal("1200.00"), security_deposit=Decimal("0.00"),
            status=LeaseStatus.ACTIVE,
        )
        db.add(lease)
        units.append(unit)
        leases.append(lease)
    db.commit()
    return users, props, units, leases




def _source(db, *, org_id: int, lease_id: int, uploader_id: int,
            name: str = "private-commercial-lease.pdf", shared: bool = False):
    row = EntityAttachment(
        organization_id=org_id, entity_type="leases", entity_id=lease_id,
        storage_key=f"commercial/{org_id}/{lease_id}/{name}",
        original_name=name, content_type="application/pdf", size_bytes=321,
        share_with_tenants=shared, share_with_owners=False,
        uploaded_by_id=uploader_id, is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def _in(lease_id, rent=date(2026, 3, 1), **extras):
    return CommercialLeaseAbstractIn(
        lease_id=lease_id, rent_commencement_on=rent, **extras,
    )


def test_commencement_is_explicit_staff_reference_not_billing():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign, _), (prop, _, _, _), _, leases = _seed(db)
        before = (db.query(Charge).count(), db.query(GLTransaction).count(),
                  db.query(RentInvoice).count())
        created = api.record_abstract(prop.id, _in(leases[0].id),
                                      db=db, current_user=admin)
        assert created.reference_status == "STAFF_RECORDED_UNVERIFIED"
        assert created.lease_start_on == date(2026, 1, 1)
        assert created.rent_commencement_on == date(2026, 3, 1)
        assert created.lease_status == LeaseStatus.ACTIVE.value
        assert "approved" not in created.model_dump()
        response = Response()
        assert [x.id for x in api.list_abstracts(prop.id, response,
                                                  db=db, current_user=manager)] == [created.id]
        assert response.headers["cache-control"] == "no-store"
        candidate_response = Response()
        assert [x.lease_id for x in api.list_candidates(prop.id, candidate_response,
                                                        db=db, current_user=manager)] == [leases[0].id]
        assert candidate_response.headers["cache-control"] == "no-store"
        with pytest.raises(HTTPException) as e:
            api.record_abstract(prop.id, _in(leases[0].id), db=db, current_user=owner)
        assert e.value.status_code == 409

        # A recorded rent date need not equal the existing Lease start date.
        edited = api.update_abstract(
            prop.id, created.id,
            CommercialLeaseAbstractUpdate(rent_commencement_on=date(2026, 4, 1)),
            db=db, current_user=owner,
        )
        assert edited.rent_commencement_on == date(2026, 4, 1)
        api.archive_abstract(prop.id, created.id, db=db, current_user=admin)
        assert api.list_abstracts(prop.id, Response(), db=db, current_user=manager) == []
        revived = api.record_abstract(prop.id, _in(leases[0].id, None),
                                      db=db, current_user=admin)
        assert revived.id == created.id
        assert revived.rent_commencement_on is None
        assert db.query(CommercialLeaseAbstract).count() == 1
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "commercial_lease_abstract",
        ).count() == 4
        assert (db.query(Charge).count(), db.query(GLTransaction).count(),
                db.query(RentInvoice).count()) == before
        assert db.get(Lease, leases[0].id).monthly_rent == Decimal("1200.00")
    finally:
        db.close()
        engine.dispose()


def test_property_and_tenant_boundaries_commercial_only():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign, other_tenant), props, units, leases = _seed(db)
        for actor, prop in ((manager, props[1]), (manager, props[3]),
                            (foreign, props[0]), (admin, props[2])):
            with pytest.raises(HTTPException) as e:
                api.list_candidates(prop.id, Response(), db=db, current_user=actor)
            assert e.value.status_code == 404
        for actor in (manager, tenant, foreign):
            with pytest.raises(HTTPException) as e:
                api.record_abstract(props[0].id, _in(leases[0].id),
                                    db=db, current_user=actor)
            assert e.value.status_code in {403, 404}
        for foreign_lease in leases[1:]:
            with pytest.raises(HTTPException) as e:
                api.record_abstract(props[0].id, _in(foreign_lease.id),
                                    db=db, current_user=admin)
            assert e.value.status_code == 404
        saved = api.record_abstract(props[0].id, _in(leases[0].id),
                                    db=db, current_user=admin)
        with pytest.raises(HTTPException) as e:
            api.update_abstract(props[1].id, saved.id,
                                CommercialLeaseAbstractUpdate(rent_commencement_on=None),
                                db=db, current_user=owner)
        assert e.value.status_code == 404
        # No tenant identity crosses org even if a lease points at a foreign user.
        leases[0].tenant_id = other_tenant.id
        db.flush()
        assert api.list_abstracts(props[0].id, Response(), db=db, current_user=admin) == []
        assert api.list_candidates(props[0].id, Response(), db=db, current_user=admin) == []
        with pytest.raises(HTTPException) as e:
            api.archive_abstract(props[0].id, saved.id, db=db, current_user=admin)
        assert e.value.status_code == 404
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def test_live_assignment_feature_leasing_and_generic_target_guards(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign, _), (prop, *_), units, leases = _seed(db)
        saved = api.record_abstract(prop.id, _in(leases[0].id),
                                    db=db, current_user=admin)
        with pytest.raises(ValidationError):
            _in(leases[0].id, approved=True)
        with pytest.raises(ValidationError):
            CommercialLeaseAbstractUpdate(cam_charge="100")
        with pytest.raises(HTTPException) as e:
            _model_for_table("commercial_lease_abstracts")
        assert e.value.status_code == 404
        db.query(PropertyAssignment).filter(
            PropertyAssignment.property_id == prop.id,
            PropertyAssignment.user_id == manager.id,
        ).one().is_active = False
        db.flush()
        with pytest.raises(HTTPException) as e:
            api.list_abstracts(prop.id, Response(), db=db, current_user=manager)
        assert e.value.status_code == 404
        monkeypatch.setattr(api, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "LEASING")
        with pytest.raises(HTTPException) as e:
            api.list_abstracts(prop.id, Response(), db=db, current_user=admin)
        assert e.value.status_code == 403
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(affordable_programs, "resolve_customer_features",
                            lambda *a, **k: [SimpleNamespace(
                                key=affordable_programs.FEATURE_KEY, allowed=False,
                            )])
        with pytest.raises(HTTPException) as e:
            api.list_abstracts(prop.id, Response(), db=db, current_user=admin)
        assert e.value.status_code == 404
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
        assert db.get(CommercialLeaseAbstract, saved.id).is_active is True
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def test_private_lease_source_is_scoped_unshared_and_removal_protected(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign, _), props, _, leases = _seed(db)
        prop = props[0]
        source = _source(
            db, org_id=admin.organization_id, lease_id=leases[0].id,
            uploader_id=admin.id,
        )
        shared = _source(
            db, org_id=admin.organization_id, lease_id=leases[0].id,
            uploader_id=admin.id, name="shared.pdf", shared=True,
        )
        wrong = _source(
            db, org_id=admin.organization_id, lease_id=leases[1].id,
            uploader_id=admin.id, name="other-lease.pdf",
        )
        db.commit()
        before = (db.query(Charge).count(), db.query(GLTransaction).count(),
                  db.query(RentInvoice).count())

        response = Response()
        choices = api.list_source_candidates(
            prop.id, response, lease_id=leases[0].id,
            db=db, current_user=manager,
        )
        assert response.headers["cache-control"] == "no-store"
        assert [row.id for row in choices] == [source.id]

        created = api.record_abstract(
            prop.id, _in(leases[0].id, source_attachment_id=source.id),
            db=db, current_user=admin,
        )
        assert created.source_attachment_id == source.id
        assert created.source_filename == source.original_name
        assert created.source_status == "STAFF_LINKED_UNVERIFIED"
        assert api.list_abstracts(
            prop.id, Response(), db=db, current_user=manager,
        )[0].source_filename == source.original_name

        with pytest.raises(HTTPException) as unsafe:
            api.update_abstract(
                prop.id, created.id,
                CommercialLeaseAbstractUpdate(source_attachment_id=shared.id),
                db=db, current_user=owner,
            )
        assert unsafe.value.status_code == 404
        with pytest.raises(HTTPException) as wrong_lease:
            api.update_abstract(
                prop.id, created.id,
                CommercialLeaseAbstractUpdate(source_attachment_id=wrong.id),
                db=db, current_user=owner,
            )
        assert wrong_lease.value.status_code == 404

        monkeypatch.setattr(
            attachments_api, "_attachment_for_user",
            lambda *a, **k: source,
        )
        monkeypatch.setattr(
            attachments_api, "_governing_evidence_scope",
            lambda *a, **k: None,
        )
        with pytest.raises(HTTPException) as sharing:
            attachments_api.update_entity_attachment_sharing(
                source.id, EntityAttachmentShareUpdate(share_with_tenants=True),
                db=db, current_user=admin,
            )
        assert sharing.value.status_code == 403
        with pytest.raises(HTTPException) as deletion:
            attachments_api.delete_entity_attachment(
                source.id, db=db, current_user=admin,
            )
        assert deletion.value.status_code == 409

        cleared = api.update_abstract(
            prop.id, created.id,
            CommercialLeaseAbstractUpdate(source_attachment_id=None),
            db=db, current_user=admin,
        )
        assert cleared.source_attachment_id is None
        assert (db.query(Charge).count(), db.query(GLTransaction).count(),
                db.query(RentInvoice).count()) == before
    finally:
        db.rollback()
        db.close()
        engine.dispose()
