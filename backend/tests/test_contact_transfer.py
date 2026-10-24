"""Contact CSV import is a bounded no-write preview followed by explicit atomic create."""
from __future__ import annotations

import csv
from io import StringIO

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.contact import Contact
from app.models.user import Organization, User, UserRole
from app.models.vendor import Vendor
from app.routers import contacts as api
from app.schemas.contact import ContactCreate
from app.services.contact_transfer import analyze_import, commit_import, export_contacts, ContactTransferError


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    one, two = Organization(name="CSV One", slug="csv-one"), Organization(name="CSV Two", slug="csv-two")
    db.add_all([one, two]); db.flush()
    users = []
    for org, role, name in (
        (one, UserRole.ADMIN, "Admin"), (one, UserRole.OWNER, "Owner"),
        (one, UserRole.MANAGER, "Manager"), (one, UserRole.TENANT, "Tenant"),
        (two, UserRole.ADMIN, "Other"),
    ):
        u = User(
            organization_id=org.id, role=role, first_name=name,
            last_name="CSV", email=f"{name.lower()}@csv-tests.example",
            hashed_password="x", is_active=True,
        )
        db.add(u); users.append(u)
    db.commit()
    return users


def _csv(*rows):
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(("display_name", "contact_type", "email", "company_name"))
    writer.writerows(rows)
    return stream.getvalue()


def test_preview_is_read_only_then_explicit_atomic_commit(monkeypatch):
    db, engine = _db()
    try:
        admin, *_ = _seed(db)
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
        text = _csv(("Sage One", "PERSON", "sage@example.com", ""),
                    ("Studio Two", "BUSINESS", "", "Studio"))
        before_users, before_vendors = db.query(User).count(), db.query(Vendor).count()
        preview = api.preview_contacts_csv(api.ContactCsvIn(csv_text=text), Response(),
                                           db=db, current_user=admin)
        assert preview["total"] == 2 and preview["can_commit"]
        assert db.query(Contact).count() == 0
        result = api.commit_contacts_csv(
            api.ContactCsvCommitIn(csv_text=text, preview_digest=preview["preview_digest"], confirm=True),
            Response(), db=db, current_user=admin,
        )
        assert result == {"created": 2}
        assert db.query(Contact).filter_by(organization_id=admin.organization_id).count() == 2
        assert db.query(User).count() == before_users
        assert db.query(Vendor).count() == before_vendors
        audit = db.query(AuditLog).filter_by(entity_type="contact_import").one()
        assert audit.new_value == '{"count":2}'
        assert "sage@example.com" not in audit.new_value
        again = api.preview_contacts_csv(api.ContactCsvIn(csv_text=text), Response(),
                                           db=db, current_user=admin)
        assert again["conflict_rows"] == [2, 3] and not again["can_commit"]
        with pytest.raises(HTTPException) as exc:
            api.commit_contacts_csv(
                api.ContactCsvCommitIn(csv_text=text, preview_digest=preview["preview_digest"], confirm=True),
                Response(), db=db, current_user=admin,
            )
        assert exc.value.status_code == 422
        assert db.query(Contact).count() == 2
    finally:
        db.close(); engine.dispose()


def test_bad_columns_duplicates_invalid_rows_and_digest_fail_without_writes():
    db, engine = _db()
    try:
        admin, *_ = _seed(db)
        for text in (
            "display_name,tin\nAlice,123456789",
            "display_name,display_name\nAlice,Bob",
            _csv(("X", "PERSON", "bad-email", "")),
            _csv((" ", "PERSON", "", "")),
            _csv(("X", "UNKNOWN", "", "")),
            _csv(*(("X" + str(i), "PERSON", "", "") for i in range(201))),
        ):
            with pytest.raises(ContactTransferError):
                analyze_import(db, organization_id=admin.organization_id, csv_text=text)
        same = _csv(("Alpha", "PERSON", "alice@example.com", ""),
                    ("Different", "PERSON", "ALICE@EXAMPLE.COM", ""))
        p = analyze_import(db, organization_id=admin.organization_id, csv_text=same)
        assert p["conflict_rows"] == [3] and not p["can_commit"]
        with pytest.raises(ContactTransferError):
            commit_import(db, organization_id=admin.organization_id,
                          actor_id=admin.id, csv_text=same, preview_digest=p["preview_digest"])
        other = _csv(("Changed", "PERSON", "", ""))
        with pytest.raises(ContactTransferError, match="changed"):
            commit_import(db, organization_id=admin.organization_id,
                          actor_id=admin.id, csv_text=other, preview_digest=p["preview_digest"])
        assert db.query(Contact).count() == 0
    finally:
        db.close(); engine.dispose()


def test_scoped_export_escapes_spreadsheet_formulas_and_excludes_archived_and_other_org(monkeypatch):
    db, engine = _db()
    try:
        admin, owner, manager, tenant, other_admin = _seed(db)
        own = Contact(organization_id=admin.organization_id, display_name="=DANGEROUS",
                      contact_type="PERSON", email="=bad@example.com")
        inactive = Contact(organization_id=admin.organization_id, display_name="Archived",
                           is_active=False)
        foreign = Contact(organization_id=other_admin.organization_id, display_name="Private",
                          email="private@example.com")
        db.add_all([own, inactive, foreign]); db.commit()
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
        from types import SimpleNamespace
        monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key="release.reporting.export", allowed=True),
        ])
        resp = api.export_contacts_csv(db=db, current_user=owner)
        assert resp.headers["cache-control"] == "no-store"
        assert resp.headers["x-content-type-options"] == "nosniff"
        txt = resp.body.decode("utf-8-sig")
        assert "'=DANGEROUS" in txt and "'=bad@example.com" in txt
        assert "Archived" not in txt and "Private" not in txt
        assert "private@example.com" not in txt
        assert db.query(Contact).count() == 3
        monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key="release.reporting.export", allowed=False),
        ])
        with pytest.raises(HTTPException) as exc:
            api.export_contacts_csv(db=db, current_user=admin)
        assert exc.value.status_code == 404
    finally:
        db.close(); engine.dispose()


def test_role_and_menu_revocation_deny_preview_commit_and_export(monkeypatch):
    db, engine = _db()
    try:
        admin, owner, manager, tenant, other_admin = _seed(db)
        text = _csv(("No Access", "PERSON", "", ""))
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
        for actor in (owner, manager, tenant):
            with pytest.raises(HTTPException) as exc:
                api.preview_contacts_csv(api.ContactCsvIn(csv_text=text), Response(),
                                         db=db, current_user=actor)
            assert exc.value.status_code == 403
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: False)
        with pytest.raises(HTTPException) as exc:
            api.preview_contacts_csv(api.ContactCsvIn(csv_text=text), Response(),
                                     db=db, current_user=admin)
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            api.commit_contacts_csv(
                api.ContactCsvCommitIn(csv_text=text, preview_digest="0"*64, confirm=True),
                Response(), db=db, current_user=admin,
            )
        assert exc.value.status_code == 403
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
        admin.is_active = False; db.commit()
        with pytest.raises(HTTPException) as exc:
            api.export_contacts_csv(db=db, current_user=admin)
        assert exc.value.status_code == 403
        assert db.query(Contact).count() == 0
    finally:
        db.close(); engine.dispose()


def test_org_bound_preview_prevents_cross_org_replay():
    db, engine = _db()
    try:
        admin, *_rest = _seed(db)
        other = _rest[-1]
        txt = _csv(("Private", "PERSON", "p@example.com", ""))
        p = analyze_import(db, organization_id=admin.organization_id, csv_text=txt)
        with pytest.raises(ContactTransferError):
            commit_import(db, organization_id=other.organization_id,
                          actor_id=other.id, csv_text=txt, preview_digest=p["preview_digest"])
        assert db.query(Contact).count() == 0
    finally:
        db.close(); engine.dispose()
