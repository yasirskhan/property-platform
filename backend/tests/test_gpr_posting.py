from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.gl_account import GLAccount, GLAccountPostingRestriction
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease, LeaseStatus
from app.models.property import Property, Unit
from app.models.user import Organization, User, UserRole
from app.services.gl_posting import PostingError
import app.services.gpr_posting as gpr


TEST_TABLES = [
    Organization.__table__,
    User.__table__,
    Property.__table__,
    Unit.__table__,
    Lease.__table__,
    GLAccount.__table__,
    GLAccountPostingRestriction.__table__,
    GLTransaction.__table__,
    GLEntry.__table__,
    AuditLog.__table__,
]


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TEST_TABLES)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=list(reversed(TEST_TABLES)))
        engine.dispose()


def seed_gpr(db: Session, slug: str = "gpr-org"):
    org = Organization(name="GPR Org", slug=slug)
    db.add(org)
    db.flush()
    user = User(
        email=f"{slug}@example.com",
        hashed_password="unused",
        first_name="GPR",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
        is_verified=True,
    )
    prop = Property(
        organization_id=org.id,
        name="GPR Property",
        property_type="MULTI_FAMILY",
        address_line1="1 Main St",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="USA",
        is_active=True,
    )
    db.add_all([user, prop])
    db.flush()
    occupied = Unit(
        property_id=prop.id,
        unit_number="1",
        bedrooms=1,
        bathrooms=1,
        monthly_rent=Decimal("1500.00"),
        is_active=True,
    )
    vacant = Unit(
        property_id=prop.id,
        unit_number="2",
        bedrooms=1,
        bathrooms=1,
        monthly_rent=Decimal("1200.00"),
        is_active=True,
    )
    db.add_all([occupied, vacant])
    db.flush()
    lease = Lease(
        unit_id=occupied.id,
        tenant_id=user.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        monthly_rent=Decimal("1400.00"),
        security_deposit=Decimal("0"),
        due_day=1,
        status=LeaseStatus.ACTIVE,
    )
    accounts = [
        GLAccount(
            organization_id=org.id,
            gl_number="4100",
            name="Rent",
            account_type="INCOME",
            is_active=True,
        ),
        GLAccount(
            organization_id=org.id,
            gl_number="4115",
            name="Gross Potential Rent",
            account_type="INCOME",
            is_active=True,
        ),
        GLAccount(
            organization_id=org.id,
            gl_number="4120",
            name="Loss/Gain",
            account_type="INCOME",
            is_active=True,
        ),
    ]
    db.add(lease)
    db.add_all(accounts)
    db.commit()
    return org, user, prop, occupied, vacant, accounts


@pytest.mark.accounting
def test_gpr_candidates_use_unit_market_rent_and_active_lease_rent(db: Session) -> None:
    org, _user, _prop, occupied, vacant, _accounts = seed_gpr(db)

    rows = gpr.list_gpr_candidates(
        db, organization_id=org.id, month=date(2026, 6, 15)
    )
    by_unit = {row.unit_id: row for row in rows}

    assert by_unit[occupied.id].market_rent == Decimal("1500.00")
    assert by_unit[occupied.id].scheduled_rent == Decimal("1400.00")
    assert by_unit[occupied.id].loss_gain == Decimal("100.00")
    assert by_unit[occupied.id].lease_id is not None

    assert by_unit[vacant.id].market_rent == Decimal("1200.00")
    assert by_unit[vacant.id].scheduled_rent == Decimal("0.00")
    assert by_unit[vacant.id].loss_gain == Decimal("1200.00")
    assert by_unit[vacant.id].lease_id is None


@pytest.mark.accounting
def test_post_gpr_is_balanced_atomic_and_idempotent(db: Session) -> None:
    org, user, _prop, occupied, vacant, accounts = seed_gpr(db)
    by_number = {row.gl_number: row for row in accounts}

    txns = gpr.post_gpr(
        db,
        organization_id=org.id,
        month=date(2026, 6, 20),
        unit_ids=[occupied.id, vacant.id],
        created_by=user,
    )

    assert len(txns) == 2
    assert {row.transaction_date for row in txns} == {date(2026, 6, 1)}
    assert {row.source_type for row in txns} == {"gpr"}
    assert {row.source_id for row in txns} == {occupied.id, vacant.id}

    entries = (
        db.query(GLEntry)
        .filter(GLEntry.transaction_id.in_([row.id for row in txns]))
        .all()
    )
    totals: dict[int, tuple[Decimal, Decimal]] = {}
    for entry in entries:
        debit, credit = totals.get(entry.gl_account_id, (Decimal("0"), Decimal("0")))
        totals[entry.gl_account_id] = (
            debit + Decimal(entry.debit or 0),
            credit + Decimal(entry.credit or 0),
        )

    assert totals[by_number["4100"].id] == (Decimal("1400.00"), Decimal("0"))
    assert totals[by_number["4115"].id] == (Decimal("0"), Decimal("2700.00"))
    assert totals[by_number["4120"].id] == (Decimal("1300.00"), Decimal("0"))

    with pytest.raises(PostingError, match="already posted"):
        gpr.post_gpr(
            db,
            organization_id=org.id,
            month=date(2026, 6, 1),
            unit_ids=[occupied.id],
            created_by=user,
        )


@pytest.mark.accounting
def test_post_gpr_rejects_unit_outside_organization(db: Session) -> None:
    org, user, _prop, occupied, _vacant, _accounts = seed_gpr(db, "gpr-main")
    other_org, _other_user, _other_prop, other_unit, _v2, _a2 = seed_gpr(
        db, "gpr-other"
    )
    assert other_org.id != org.id
    assert other_unit.id != occupied.id

    with pytest.raises(PostingError, match="not active in this organization"):
        gpr.post_gpr(
            db,
            organization_id=org.id,
            month=date(2026, 7, 1),
            unit_ids=[other_unit.id],
            created_by=user,
        )
