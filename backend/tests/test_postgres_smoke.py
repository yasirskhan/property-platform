from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "e6b4d2a7c910"
EXPECTED_MODEL_TABLES = 214


@pytest.mark.integration
def test_postgres_fresh_bootstrap_when_ci_database_is_available() -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url or not url.startswith("postgresql"):
        pytest.skip("TEST_DATABASE_URL PostgreSQL service is only required in CI/staging")

    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()

    env = os.environ.copy()
    env["DATABASE_URL"] = url
    result = subprocess.run(
        [sys.executable, "bootstrap_fresh_db.py"],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"PostgreSQL bootstrap failed:\n{result.stdout}\n{result.stderr}"
    )

    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "alembic_version" in tables
        assert len(tables - {"alembic_version"}) == EXPECTED_MODEL_TABLES
        assert next(col for col in inspect(engine).get_columns(
            "preventive_maintenance_schedules"
        ) if col["name"] == "end_date")["nullable"] is True
        assert next(col for col in inspect(engine).get_columns(
            "preventive_maintenance_schedules"
        ) if col["name"] == "executor_user_id")["nullable"] is True
        assert any(
            fk["referred_table"] == "users"
            and fk["constrained_columns"] == ["executor_user_id"]
            for fk in inspect(engine).get_foreign_keys("preventive_maintenance_schedules")
        ), "Preventive execution operator must use an enforced PostgreSQL FK"

        cols = {col["name"]: col for col in inspect(engine).get_columns("work_orders")}
        assert cols["assignment_response"]["nullable"] is True
        assert cols["assignment_responded_at"]["nullable"] is True
        assert cols["crew_eta_at"]["nullable"] is True
        assert "maintenance_on_call_shifts" in tables
        assert any(fk["referred_table"] == "users" and fk["constrained_columns"] == ["crew_user_id"]
                   for fk in inspect(engine).get_foreign_keys("maintenance_on_call_shifts"))
        assert "maintenance_preferred_vendors" in tables
        assert any(fk["referred_table"] == "vendors"
                   and fk["constrained_columns"] == ["vendor_id"]
                   for fk in inspect(engine).get_foreign_keys("maintenance_preferred_vendors"))
        assert "work_order_time_corrections" in tables
        assert any(fk["referred_table"] == "work_order_time_entries" for fk in inspect(engine).get_foreign_keys("work_order_time_corrections"))
        assert "work_order_time_entries" in tables
        assert next(c for c in inspect(engine).get_columns("work_order_time_entries") if c["name"] == "duration_minutes")["nullable"] is False
        with engine.connect() as conn:
            triggers = set(conn.execute(text(
                "SELECT tgname FROM pg_trigger WHERE tgrelid = 'work_order_time_entries'::regclass "
                "AND NOT tgisinternal"
            )).scalars())
        assert "crew_time_immutable" in triggers
        assert cols["tenant_id"]["nullable"] is True
        source_fks = inspect(engine).get_foreign_keys("work_orders")
        assert any(
            fk["referred_table"] == "unit_inspection_records"
            and fk["constrained_columns"] == ["source_inspection_id"]
            for fk in source_fks
        ), "The source inspection link must have an enforced PostgreSQL FK"

        with engine.connect() as conn:
            version = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert version == EXPECTED_HEAD

        with engine.begin() as conn:
            audit_id = conn.execute(
                text(
                    "INSERT INTO audit_log "
                    "(entity_type, entity_id, action, created_at) "
                    "VALUES ('ci_probe', 1, 'created', CURRENT_TIMESTAMP) "
                    "RETURNING id"
                )
            ).scalar_one()

        with pytest.raises(DBAPIError, match="append-only"):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE audit_log SET action='tampered' WHERE id=:id"
                    ),
                    {"id": audit_id},
                )

        with pytest.raises(DBAPIError, match="append-only"):
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM audit_log WHERE id=:id"),
                    {"id": audit_id},
                )

        with engine.begin() as conn:
            org_id = conn.execute(
                text(
                    "INSERT INTO organizations "
                    "(name, slug, state, currency, data_region, created_at, updated_at) "
                    "VALUES "
                    "('Billing Probe', 'billing-probe', 'ACTIVE', 'USD', "
                    "'us-east-1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                    "RETURNING id"
                )
            ).scalar_one()
            plan_id = conn.execute(
                text(
                    "INSERT INTO plans "
                    "(code, name, is_active, created_at, updated_at) "
                    "VALUES "
                    "('ci-probe', 'CI Probe', true, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                    "RETURNING id"
                )
            ).scalar_one()
            subscription_id = conn.execute(
                text(
                    "INSERT INTO subscriptions "
                    "(organization_id, plan_id, status, cancel_at_period_end, "
                    "created_at, updated_at) "
                    "VALUES "
                    "(:org_id, :plan_id, 'ACTIVE', false, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                    "RETURNING id"
                ),
                {"org_id": org_id, "plan_id": plan_id},
            ).scalar_one()
            event_id = conn.execute(
                text(
                    "INSERT INTO subscription_events "
                    "(subscription_id, event_type, created_at) "
                    "VALUES (:subscription_id, 'created', CURRENT_TIMESTAMP) "
                    "RETURNING id"
                ),
                {"subscription_id": subscription_id},
            ).scalar_one()

        with pytest.raises(DBAPIError, match="append-only"):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE subscription_events "
                        "SET event_type='tampered' WHERE id=:id"
                    ),
                    {"id": event_id},
                )

        with pytest.raises(DBAPIError, match="append-only"):
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM subscription_events WHERE id=:id"),
                    {"id": event_id},
                )
    finally:
        engine.dispose()
