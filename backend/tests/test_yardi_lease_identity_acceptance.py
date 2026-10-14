"""Yardi lease identity acceptance records review metadata only; never a Lease."""
import pytest
from fastapi import HTTPException, Response

from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Property, Unit
from app.models.user import User, UserRole
from app.routers.yardi_migrations import (
    accept_yardi_staged_lease_relationship,
    get_yardi_reconciliation,
    list_yardi_lease_relationships,
    dry_run_yardi_review,
    skip_yardi_staged_row,
    YardiRowSkipIn,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def _seed(db, slug="yardi-lease-identity-accept", *, lease_property="P1", unit_property="P1"):
    actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
    org = _org(db, slug)
    original = Property(
        organization_id=org.id, name="Original", address_line1="1 Main",
        city="Cleveland", state="OH", zip_code="44113",
    )
    alternate = Property(
        organization_id=org.id, name="Alternate", address_line1="2 Main",
        city="Cleveland", state="OH", zip_code="44113",
    )
    tenant = User(
        organization_id=org.id, role=UserRole.TENANT,
        email=slug + "@example.test", hashed_password="unchanged-password-hash",
        first_name="Existing", last_name="Tenant", is_active=True,
    )
    run = PlatformMigrationRun(
        organization_id=org.id, provider="YARDI",
        source_account_ref="reviewed-source", status="DRAFT",
    )
    db.add_all([original, alternate, tenant, run])
    db.flush()
    unit = Unit(property_id=original.id if unit_property == "P1" else alternate.id,
                unit_number="101")
    db.add(unit)
    db.flush()
    for resource, source, entity, target in (
        ("PROPERTIES", "P1", "PROPERTY", original.id),
        ("PROPERTIES", "P2", "PROPERTY", alternate.id),
        ("TENANTS", "T1", "TENANT_USER", tenant.id),
    ):
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource=resource, source_id=source,
            target_entity=entity, target_id=target,
            source_fingerprint="reviewed-" + source,
        ))
    db.commit()
    unit_upload = stage_yardi_file(
        db, run=run, filename="units.csv",
        content=b"Unit,Parent,Label\nU1,P1,101\n",
        resource_override="UNITS", sheet_name=None,
        explicit_mapping={
            "source_id": "Unit", "source_property_id": "Parent",
            "unit_name": "Label",
        }, platform_user_id=actor.id,
    )
    db.commit()
    unit_row = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.upload_id == unit_upload.upload.id,
    ).one()
    unit_row.resolution_action = "MATCH_EXISTING"
    unit_row.resolution_target_unit_id = unit.id
    db.add(PlatformMigrationItem(
        run_id=run.id, organization_id=org.id, provider="YARDI",
        resource="UNITS", source_id="U1", target_entity="UNIT",
        target_id=unit.id, source_fingerprint=unit_row.row_fingerprint,
    ))
    db.commit()
    lease_upload = stage_yardi_file(
        db, run=run, filename="leases.csv",
        content=(
            b"Lease,Tenant,Property,Unit\n"
            + f"L1,T1,{lease_property},U1\n".encode()
        ),
        resource_override="LEASE_OCCUPANCY", sheet_name=None,
        explicit_mapping={
            "source_id": "Lease", "source_tenant_id": "Tenant",
            "source_property_id": "Property", "source_unit_id": "Unit",
        }, platform_user_id=actor.id,
    )
    db.commit()
    lease_row = db.query(PlatformMigrationStagedRow).filter(
        PlatformMigrationStagedRow.upload_id == lease_upload.upload.id,
    ).one()
    return actor, org, run, original, alternate, unit, tenant, lease_row


def test_yardi_lease_review_acceptance_replays_and_preserves_customer_data():
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, row = _seed(db)
        original_lease_count = db.query(Lease).count()
        mapping_count = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count()
        snapshot = dry_run_yardi_review(run.id, db, actor)
        assert snapshot["review_fingerprint"]
        accepted = accept_yardi_staged_lease_relationship(run.id, row.id, db, actor)
        assert accepted["action"] == "ACCEPT_RELATIONSHIP"
        assert accepted["replayed"] is False
        assert accepted["customer_business_mutation"] is False
        db.refresh(row)
        db.refresh(run)
        assert row.resolution_target_id == original.id
        assert row.resolution_target_unit_id == unit.id
        assert row.resolution_target_tenant_user_id == tenant.id
        assert run.last_dry_run_fingerprint is None
        assert row.resolved_by_platform_user_id == actor.id
        assert any(e.get("action") == "ACCEPT_RELATIONSHIP" for e in row.correction_evidence)
        stats = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert stats["resource_coverage"]["LEASE_OCCUPANCY"]["accepted_relationship_review"] == 1
        relationship = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )
        assert relationship["items"][0]["relationship_review_recorded"] is True
        assert relationship["items"][0]["relationship_review_current"] is True
        assert relationship["items"][0]["blockers"] == []
        assert relationship["items"][0]["occupancy_or_lease_authorized"] is False
        again = accept_yardi_staged_lease_relationship(run.id, row.id, db, actor)
        assert again["replayed"] is True
        assert db.query(Lease).count() == original_lease_count
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count() == mapping_count
        db.refresh(tenant)
        assert tenant.hashed_password == "unchanged-password-hash"
        unit.property_id = alternate.id
        db.commit()
        with pytest.raises(HTTPException) as stale:
            accept_yardi_staged_lease_relationship(run.id, row.id, db, actor)
        assert stale.value.status_code == 409
        moved_preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )
        assert moved_preview["items"][0]["relationship_review_recorded"] is True
        assert moved_preview["items"][0]["relationship_review_current"] is False
        assert "UNIT_PROPERTY_MISMATCH" in moved_preview["items"][0]["blockers"]
        assert db.query(Lease).count() == original_lease_count
    finally:
        db.close()
        engine.dispose()


def test_yardi_lease_accept_rejects_source_parent_disagreement_even_if_target_matches():
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, row = _seed(
            db, "yardi-lease-source-disagree", lease_property="P2", unit_property="P2",
        )
        assert unit.property_id == alternate.id
        with pytest.raises(HTTPException) as conflict:
            accept_yardi_staged_lease_relationship(run.id, row.id, db, actor)
        assert conflict.value.status_code == 409
        db.refresh(row)
        assert row.resolution_action is None
        assert db.query(Lease).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_yardi_lease_accept_needs_exact_reviewed_unit_evidence():
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, row = _seed(
            db, "yardi-lease-unverified-unit-evidence",
        )
        unit_map = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "UNITS",
        ).one()
        unit_map.source_fingerprint = "different-unreviewed-fingerprint"
        db.commit()
        with pytest.raises(HTTPException) as unverified:
            accept_yardi_staged_lease_relationship(run.id, row.id, db, actor)
        assert unverified.value.status_code == 409
        db.refresh(row)
        assert row.resolution_action is None
    finally:
        db.close()
        engine.dispose()


def test_yardi_lease_accept_blocks_cross_upload_duplicate_until_explicit_skip():
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, row = _seed(
            db, "yardi-lease-duplicate-review",
        )
        extra = stage_yardi_file(
            db, run=run, filename="lease-revision.csv",
            content=b"Lease,Tenant,Property,Unit\nL1,T1,P2,U1\n",
            resource_override="LEASE_OCCUPANCY", sheet_name=None,
            explicit_mapping={
                "source_id": "Lease", "source_tenant_id": "Tenant",
                "source_property_id": "Property", "source_unit_id": "Unit",
            }, platform_user_id=actor.id,
        )
        db.commit()
        duplicate = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == extra.upload.id,
        ).one()
        with pytest.raises(HTTPException) as duplicate_error:
            accept_yardi_staged_lease_relationship(run.id, row.id, db, actor)
        assert duplicate_error.value.status_code == 409
        skip_yardi_staged_row(
            run.id, duplicate.id, YardiRowSkipIn(reason_code="DUPLICATE_SOURCE"),
            db, actor,
        )
        accepted = accept_yardi_staged_lease_relationship(run.id, row.id, db, actor)
        assert accepted["replayed"] is False
    finally:
        db.close()
        engine.dispose()


def test_yardi_lease_accept_requires_write_role_and_correct_run_row():
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, row = _seed(
            db, "yardi-lease-accept-permissions",
        )
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        with pytest.raises(HTTPException) as forbidden:
            accept_yardi_staged_lease_relationship(run.id, row.id, db, support)
        assert forbidden.value.status_code == 403
        with pytest.raises(HTTPException) as wrong_run:
            accept_yardi_staged_lease_relationship(run.id + 1000, row.id, db, actor)
        assert wrong_run.value.status_code == 404
        skip_yardi_staged_row(
            run.id, row.id, YardiRowSkipIn(reason_code="NOT_IN_SCOPE"),
            db, actor,
        )
        with pytest.raises(HTTPException) as reviewed:
            accept_yardi_staged_lease_relationship(run.id, row.id, db, actor)
        assert reviewed.value.status_code == 409
    finally:
        db.close()
        engine.dispose()


def test_yardi_lease_accept_rejects_ambiguous_exact_unit_source_parent_reviews():
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, row = _seed(
            db, "yardi-lease-unit-source-ambiguity",
        )
        verified = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.resource == "UNITS",
        ).one()
        db.add(PlatformMigrationStagedRow(
            upload_id=verified.upload_id, run_id=run.id,
            organization_id=org.id, provider="YARDI",
            resource="UNITS", row_number=verified.row_number + 100,
            source_id=verified.source_id, disposition="REVIEW",
            row_fingerprint=verified.row_fingerprint,
            normalized_data={"source_id": "U1", "source_property_id": "P2", "unit_name": "101"},
            correction_evidence=[], warnings=[], errors=[],
            resolution_action="MATCH_EXISTING", resolution_target_unit_id=unit.id,
        ))
        db.commit()
        with pytest.raises(HTTPException) as conflict:
            accept_yardi_staged_lease_relationship(run.id, row.id, db, actor)
        assert conflict.value.status_code == 409
        db.refresh(row)
        assert row.resolution_action is None
        assert db.query(Lease).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_accepted_lease_preview_rejects_conflicting_exact_unit_parent_versions():
    """Later matching evidence must not hide an earlier conflicting version."""
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, "yardi-accepted-lease-ambiguous-parent",
        )
        accepted = accept_yardi_staged_lease_relationship(
            run.id, lease_row.id, db, actor,
        )
        assert accepted["replayed"] is False
        verified = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.resource == "UNITS",
        ).one()
        # Same reviewed identity/fingerprint but contradictory staged evidence;
        # final matching row would previously overwrite the conflict in preview.
        for i, source_parent in enumerate(("P2", "P1"), start=1):
            db.add(PlatformMigrationStagedRow(
                upload_id=verified.upload_id, run_id=run.id,
                organization_id=org.id, provider="YARDI",
                resource="UNITS", row_number=verified.row_number + i * 100,
                source_id=verified.source_id, disposition="REVIEW",
                row_fingerprint=verified.row_fingerprint,
                normalized_data={
                    "source_id": "U1", "source_property_id": source_parent,
                    "unit_name": "101",
                },
                correction_evidence=[], warnings=[], errors=[],
                resolution_action="MATCH_EXISTING",
                resolution_target_unit_id=unit.id,
            ))
        db.commit()
        preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert preview["relationship_review_recorded"] is True
        assert preview["relationship_review_current"] is False
        assert preview["unit_source_parent_matches_lease"] is False
        assert "UNIT_SOURCE_PARENT_MISMATCH" in preview["blockers"]
        assert "ACCEPTED_RELATIONSHIP_STALE" in preview["blockers"]
        summary = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert summary["lease_relationship_readiness"]["unit_source_parent_mismatch"] == 1
        assert summary["lease_relationship_readiness"]["complete_identity_links"] == 0
        with pytest.raises(HTTPException) as conflicting:
            accept_yardi_staged_lease_relationship(
                run.id, lease_row.id, db, actor,
            )
        assert conflicting.value.status_code == 409
        assert db.query(Lease).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_accepted_lease_preview_rejects_invalid_exact_unit_review_version():
    """Invalid reviewed exact evidence cannot keep an accepted relationship current."""
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, "yardi-accepted-lease-invalid-parent-review",
        )
        accept_yardi_staged_lease_relationship(run.id, lease_row.id, db, actor)
        reviewed = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.resource == "UNITS",
        ).one()
        db.add(PlatformMigrationStagedRow(
            upload_id=reviewed.upload_id, run_id=run.id,
            organization_id=org.id, provider="YARDI",
            resource="UNITS", row_number=reviewed.row_number + 100,
            source_id=reviewed.source_id, disposition="INVALID",
            row_fingerprint=reviewed.row_fingerprint,
            normalized_data={"source_id": "U1", "source_property_id": "P1", "unit_name": "101"},
            correction_evidence=[], warnings=[], errors=["UNREVIEWED_INVALID_DATA"],
            resolution_action="MATCH_EXISTING", resolution_target_unit_id=unit.id,
        ))
        db.commit()
        preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert preview["relationship_review_recorded"] is True
        assert preview["relationship_review_current"] is False
        assert preview["unit_source_parent_matches_lease"] is False
        assert "ACCEPTED_RELATIONSHIP_STALE" in preview["blockers"]
        summary = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert summary["lease_relationship_readiness"]["unit_source_parent_mismatch"] == 1
        assert summary["lease_relationship_readiness"]["complete_identity_links"] == 0
        with pytest.raises(HTTPException) as invalid:
            accept_yardi_staged_lease_relationship(run.id, lease_row.id, db, actor)
        assert invalid.value.status_code == 409
        assert db.query(Lease).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_accepted_lease_review_preview_detects_cross_upload_new_version_and_skip_resolution():
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, row = _seed(
            db, "yardi-accepted-lease-new-duplicate",
        )
        accepted = accept_yardi_staged_lease_relationship(run.id, row.id, db, actor)
        assert accepted["replayed"] is False
        added = stage_yardi_file(
            db, run=run, filename="revision.csv",
            content=b"Lease,Tenant,Property,Unit\nL1,T1,P2,U1\n",
            resource_override="LEASE_OCCUPANCY", sheet_name=None,
            explicit_mapping={
                "source_id": "Lease", "source_tenant_id": "Tenant",
                "source_property_id": "Property", "source_unit_id": "Unit",
            }, platform_user_id=actor.id,
        )
        db.commit()
        preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=1, db=db, current_user=actor,
        )
        assert preview["total"] == 2
        assert preview["items"][0]["relationship_review_recorded"] is True
        assert preview["items"][0]["relationship_review_current"] is False
        assert preview["items"][0]["blockers"] == ["LEASE_SOURCE_ID_COLLISION"]
        duplicate = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == added.upload.id,
        ).one()
        skip_yardi_staged_row(
            run.id, duplicate.id, YardiRowSkipIn(reason_code="DUPLICATE_SOURCE"),
            db, actor,
        )
        restored = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=1, db=db, current_user=actor,
        )
        assert restored["items"][0]["relationship_review_current"] is True
        assert restored["items"][0]["blockers"] == []
        assert db.query(Lease).count() == 0
    finally:
        db.close()
        engine.dispose()
