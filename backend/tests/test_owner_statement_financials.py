from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.gl_account import GLAccount
from app.models.property import Property, PropertyType
from app.models.user import Organization, User, UserRole
from app.schemas.gl_transaction import PostingLine
from app.services.gl_posting import post_transaction
from app.services.owner_statements import (
    generate_owner_statement,
    preview_owner_statement,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Owner Statement Financials", slug="owner-statement-financials")
    db.add(org)
    db.flush()
    owner = User(
        email="owner-statement-owner@example.com",
        hashed_password="x",
        first_name="Statement",
        last_name="Owner",
        role=UserRole.OWNER,
        organization_id=org.id,
        is_active=True,
    )
    admin = User(
        email="owner-statement-admin@example.com",
        hashed_password="x",
        first_name="Statement",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    prop = Property(
        organization_id=org.id,
        name="Reserve Property",
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="100 Reserve Ave",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        required_reserve_amount=Decimal("75.00"),
        is_active=True,
    )
    cash = GLAccount(
        organization_id=org.id,
        gl_number="1150",
        name="Rental Trust",
        account_type="ASSET",
        is_active=True,
    )
    prepayment = GLAccount(
        organization_id=org.id,
        gl_number="2300",
        name="Prepayment",
        account_type="LIABILITY",
        is_active=True,
    )
    db.add_all([owner, admin, prop, cash, prepayment])
    db.flush()
    prop.owner_id = owner.id
    db.commit()
    return org, owner, admin, prop, cash, prepayment


def _post_prepayment(db, *, org, admin, prop, cash, prepayment, when, amount):
    post_transaction(
        db=db,
        organization_id=org.id,
        transaction_date=when,
        transaction_type="RECEIPT",
        memo="Prepaid rent",
        created_by=admin,
        lines=[
            PostingLine(
                gl_account_id=cash.id,
                property_id=prop.id,
                debit=Decimal(amount),
            ),
            PostingLine(
                gl_account_id=prepayment.id,
                property_id=prop.id,
                credit=Decimal(amount),
            ),
        ],
    )


def test_owner_statement_freezes_required_reserves_prepaid_rent_and_available_cash():
    db, engine = _session()
    try:
        org, owner, admin, prop, cash, prepayment = _seed(db)
        _post_prepayment(
            db,
            org=org,
            admin=admin,
            prop=prop,
            cash=cash,
            prepayment=prepayment,
            when=date(2026, 9, 10),
            amount="200.00",
        )

        preview = preview_owner_statement(
            db,
            organization_id=org.id,
            owner_id=owner.id,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
        )
        row = preview["properties"][0]
        assert row["ending_cash"] == "200.00"
        assert row["required_reserves"] == "75.00"
        assert row["prepaid_rent"] == "200.00"
        assert row["available_cash"] == "-75.00"
        assert preview["total_required_reserves"] == Decimal("75.00")
        assert preview["total_prepaid_rent"] == Decimal("200.00")
        assert preview["total_available_cash"] == Decimal("-75.00")

        statement = generate_owner_statement(
            db,
            organization_id=org.id,
            owner_id=owner.id,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            notes=None,
            created_by=admin,
        )
        frozen = json.loads(statement.property_data)
        assert frozen[0]["required_reserves"] == "75.00"
        assert frozen[0]["prepaid_rent"] == "200.00"
        assert frozen[0]["available_cash"] == "-75.00"

        prop.required_reserve_amount = Decimal("999.00")
        db.commit()
        assert json.loads(statement.property_data)[0]["required_reserves"] == "75.00"
    finally:
        db.close()
        engine.dispose()


def test_owner_statement_prepaid_rent_uses_period_end_scope():
    db, engine = _session()
    try:
        org, owner, admin, prop, cash, prepayment = _seed(db)
        _post_prepayment(
            db,
            org=org,
            admin=admin,
            prop=prop,
            cash=cash,
            prepayment=prepayment,
            when=date(2026, 9, 15),
            amount="40.00",
        )
        _post_prepayment(
            db,
            org=org,
            admin=admin,
            prop=prop,
            cash=cash,
            prepayment=prepayment,
            when=date(2026, 10, 1),
            amount="60.00",
        )

        preview = preview_owner_statement(
            db,
            organization_id=org.id,
            owner_id=owner.id,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
        )
        assert preview["properties"][0]["prepaid_rent"] == "40.00"
        assert preview["properties"][0]["ending_cash"] == "40.00"
    finally:
        db.close()
        engine.dispose()
