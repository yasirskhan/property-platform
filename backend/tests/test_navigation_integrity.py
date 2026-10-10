"""Navigation readiness and static route-integrity regressions."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import check_navigation
import init_db  # noqa: F401
from app.constants.menu_keys import MENU_ROUTE_BLOCKED_UNTIL
from app.core.database import Base
from app.models.user import Organization, User, UserRole
from app.services.menu_resolver import resolve_menu_for_user


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def test_navigation_source_contract_is_clean() -> None:
    assert check_navigation.main() == 0


def test_unready_routes_never_reach_admin_resolved_menu() -> None:
    db, engine = _session()
    try:
        org = Organization(name="Navigation", slug="navigation-readiness")
        db.add(org)
        db.flush()
        admin = User(
            email="navigation@example.com",
            hashed_password="unused",
            first_name="Navigation",
            last_name="Admin",
            role=UserRole.ADMIN,
            organization_id=org.id,
            is_active=True,
        )
        db.add(admin)
        db.commit()

        keys = {item["key"] for item in resolve_menu_for_user(db, admin)}
        assert "DASHBOARD" in keys
        assert "REPORTING" in keys
        assert "REPORTING.BUILDER" in keys
        assert "LEASING" in keys
        assert "PROPERTIES" in keys
        assert "PEOPLE" in keys
        assert "ACCOUNTING" in keys

        for key in MENU_ROUTE_BLOCKED_UNTIL:
            assert key not in keys

        # Entire future containers disappear rather than falling through as
        # broken leaf links after all of their children are hidden.
        assert "MAINTENANCE" not in keys
        assert "COMMUNICATION" not in keys
    finally:
        db.close()
        engine.dispose()
