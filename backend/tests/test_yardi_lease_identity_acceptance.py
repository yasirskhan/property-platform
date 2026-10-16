"""Yardi lease identity acceptance records review metadata only; never a Lease."""
import pytest
from sqlalchemy import event
from fastapi import HTTPException, Response

from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Property, Unit
from app.models.user import User, UserRole
from app.routers.yardi_migrations import (
    accept_yardi_staged_lease_relationship,
    get_yardi_reconciliation,
    list_yardi_source_collisions,
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


def test_accepted_lease_summary_excludes_stale_valid_target_identity_drift():
    """All mapped IDs may stay valid while an accepted review snapshot is stale."""
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, "yardi-accepted-lease-target-drift",
        )
        accepted = accept_yardi_staged_lease_relationship(
            run.id, lease_row.id, db, actor,
        )
        assert accepted["replayed"] is False
        good = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert good["lease_relationship_readiness"]["complete_identity_links"] == 1
        assert good["lease_relationship_readiness"]["accepted_relationship_stale"] == 0
        replacement = User(
            organization_id=org.id, role=UserRole.TENANT,
            email="yardi-accepted-target-drift-replacement@example.test",
            hashed_password="preserve-replacement-hash",
            first_name="Another", last_name="Existing",
            is_active=True,
        )
        db.add(replacement)
        db.flush()
        tenant_link = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "TENANTS",
            PlatformMigrationItem.source_id == "T1",
        ).one()
        tenant_link.target_id = replacement.id
        db.commit()
        preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert preview["relationship_review_recorded"] is True
        assert preview["relationship_review_current"] is False
        assert preview["blockers"] == ["ACCEPTED_RELATIONSHIP_STALE"]
        summary = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert summary["lease_relationship_readiness"]["complete_identity_links"] == 0
        assert summary["lease_relationship_readiness"]["accepted_relationship_stale"] == 1
        assert summary["lease_relationship_readiness"]["lease_source_id_collisions"] == 0
        with pytest.raises(HTTPException) as stale:
            accept_yardi_staged_lease_relationship(run.id, lease_row.id, db, actor)
        assert stale.value.status_code == 409
        assert db.query(Lease).count() == 0
        db.refresh(replacement)
        assert replacement.hashed_password == "preserve-replacement-hash"
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




def test_skip_new_unit_source_version_preserves_exact_durable_review_anchor():
    """Later duplicate uploads can be dispositioned without erasing a bound Unit."""
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, "yardi-bound-unit-duplicate-skip",
        )
        source_row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.resource == "UNITS",
        ).one()
        bound = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "UNITS",
            PlatformMigrationItem.source_id == "U1",
        ).one()
        original_binding = (bound.id, bound.target_id, bound.source_fingerprint)
        upload = stage_yardi_file(
            db, run=run, filename="changed-unit-source.csv",
            content=b"Unit,Parent,Label\nU1,P2,101\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "Unit", "source_property_id": "Parent",
                "unit_name": "Label",
            }, platform_user_id=actor.id,
        )
        db.commit()
        duplicate = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        before = list_yardi_source_collisions(
            run.id, Response(), resource="UNITS", offset=0, limit=20,
            db=db, current_user=actor,
        )
        assert before["items"][0]["disposition_status"] == "UNRESOLVED_MULTIPLE"
        with pytest.raises(HTTPException) as cannot_skip_original:
            skip_yardi_staged_row(
                run.id, source_row.id, YardiRowSkipIn(reason_code="DUPLICATE_SOURCE"),
                db, actor,
            )
        assert cannot_skip_original.value.status_code == 409

        # A durable ID alone is insufficient: staff must preserve a distinct
        # source-fingerprint/target-matched, valid reviewed source row.
        source_row.row_fingerprint = "no-longer-equal-to-bound-fingerprint"
        db.commit()
        with pytest.raises(HTTPException) as missing_anchor:
            skip_yardi_staged_row(
                run.id, duplicate.id, YardiRowSkipIn(reason_code="DUPLICATE_SOURCE"),
                db, actor,
            )
        assert missing_anchor.value.status_code == 409
        source_row.row_fingerprint = bound.source_fingerprint
        db.commit()

        dry_run_yardi_review(run.id, db, actor)
        db.refresh(run)
        assert run.last_dry_run_fingerprint
        skipped = skip_yardi_staged_row(
            run.id, duplicate.id, YardiRowSkipIn(reason_code="DUPLICATE_SOURCE"),
            db, actor,
        )
        assert skipped["action"] == "SKIP"
        assert skipped["replayed"] is False
        repeated = skip_yardi_staged_row(
            run.id, duplicate.id, YardiRowSkipIn(reason_code="DUPLICATE_SOURCE"),
            db, actor,
        )
        assert repeated["replayed"] is True
        with pytest.raises(HTTPException) as changed_reason:
            skip_yardi_staged_row(
                run.id, duplicate.id, YardiRowSkipIn(reason_code="NOT_IN_SCOPE"),
                db, actor,
            )
        assert changed_reason.value.status_code == 409

        db.refresh(run)
        db.refresh(bound)
        db.refresh(source_row)
        assert run.last_dry_run_fingerprint is None
        assert (bound.id, bound.target_id, bound.source_fingerprint) == original_binding
        assert source_row.resolution_action == "MATCH_EXISTING"
        after = list_yardi_source_collisions(
            run.id, Response(), resource="UNITS", offset=0, limit=20,
            db=db, current_user=actor,
        )
        assert after["items"][0]["disposition_status"] == "ONE_UNSKIPPED"
        assert after["items"][0]["skipped_rows"] == 1
        assert db.query(Lease).count() == 0
        db.refresh(tenant)
        assert tenant.hashed_password == "unchanged-password-hash"
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
        before_duplicate = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert before_duplicate["lease_relationship_readiness"]["complete_identity_links"] == 1
        assert before_duplicate["lease_relationship_readiness"]["lease_source_id_collisions"] == 0
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
        conflicted_summary = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert conflicted_summary["lease_relationship_readiness"]["complete_identity_links"] == 0
        assert conflicted_summary["lease_relationship_readiness"]["lease_source_id_collisions"] == 2
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
        corrected_summary = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert corrected_summary["lease_relationship_readiness"]["complete_identity_links"] == 1
        assert corrected_summary["lease_relationship_readiness"]["lease_source_id_collisions"] == 0
        assert corrected_summary["lease_relationship_readiness"]["customer_business_mutation"] is False
        assert db.query(Lease).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_yardi_invalid_accepted_lease_does_not_count_as_valid_review_coverage():
    """Preserve historical acceptance but report invalid source as invalid."""
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, "yardi-invalid-accepted-coverage",
        )
        accept_yardi_staged_lease_relationship(
            run.id, lease_row.id, db, actor,
        )
        before = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert before["resource_coverage"]["LEASE_OCCUPANCY"]["accepted_relationship_review"] == 1
        lease_row.disposition = "INVALID"
        db.commit()
        result = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert result["resource_coverage"]["LEASE_OCCUPANCY"]["accepted_relationship_review"] == 0
        assert result["resource_coverage"]["LEASE_OCCUPANCY"]["invalid"] == 1
        assert result["lease_relationship_readiness"]["complete_identity_links"] == 0
        assert result["invalid_rows"] == 1
        db.refresh(lease_row)
        assert lease_row.resolution_action == "ACCEPT_RELATIONSHIP"
        assert db.query(Lease).count() == 0
        db.refresh(tenant)
        assert tenant.hashed_password == "unchanged-password-hash"
    finally:
        db.close()
        engine.dispose()


def test_yardi_aggregate_unit_match_requires_active_unit_and_parent_property():
    """Historical unit review cannot make inactive customer resources ready."""
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, "yardi-unit-aggregate-target-active",
        )
        before = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert before["resource_coverage"]["UNITS"]["matched_existing"] == 1
        unit.is_active = False
        db.commit()
        inactive_unit = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert inactive_unit["resource_coverage"]["UNITS"]["matched_existing"] == 0
        assert inactive_unit["resource_coverage"]["UNITS"]["needs_review"] == 1
        unit.is_active = True
        original.deleted_at = __import__("datetime").datetime.utcnow()
        db.commit()
        inactive_parent = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert inactive_parent["resource_coverage"]["UNITS"]["matched_existing"] == 0
        assert inactive_parent["resource_coverage"]["UNITS"]["needs_review"] == 1
        assert inactive_parent["review_fingerprint"] != before["review_fingerprint"]
        db.refresh(unit)
        db.refresh(tenant)
        assert unit.property_id == original.id
        assert tenant.hashed_password == "unchanged-password-hash"
        assert db.query(Lease).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_yardi_aggregate_review_target_drift_cannot_count_as_matched_existing():
    """A historical exact review is stale after its durable binding drifts."""
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, "yardi-aggregate-durable-unit-drift",
        )
        reviewed = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.resource == "UNITS",
        ).one()
        bound = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "UNITS",
        ).one()
        good = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert good["resource_coverage"]["UNITS"]["matched_existing"] == 1
        assert good["resource_coverage"]["UNITS"]["needs_review"] == 0
        original_binding = bound.source_fingerprint
        bound.source_fingerprint = "review-was-not-for-this-source-version"
        db.commit()
        stale_version = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert stale_version["resource_coverage"]["UNITS"]["matched_existing"] == 0
        assert stale_version["resource_coverage"]["UNITS"]["needs_review"] == 1
        assert stale_version["review_fingerprint"] != good["review_fingerprint"]
        bound.source_fingerprint = original_binding
        db.commit()
        restored = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored["resource_coverage"]["UNITS"]["matched_existing"] == 1
        # A valid same-property alternate Unit ID still disagrees with the
        # one the staff reviewed; it must not appear ready.
        sibling = Unit(property_id=original.id, unit_number="102")
        db.add(sibling)
        db.flush()
        bound.target_id = sibling.id
        db.commit()
        stale_target = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert stale_target["resource_coverage"]["UNITS"]["matched_existing"] == 0
        assert stale_target["resource_coverage"]["UNITS"]["needs_review"] == 1
        assert reviewed.resolution_action == "MATCH_EXISTING"
        assert db.query(Lease).count() == 0
        db.refresh(tenant)
        assert tenant.hashed_password == "unchanged-password-hash"
    finally:
        db.close()
        engine.dispose()


def test_yardi_unskipped_duplicate_unit_source_invalidates_existing_review_and_lease_acceptance():
    """New unskipped identity versions cannot inherit prior durable review."""
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, "yardi-durable-duplicate-coverage",
        )
        accept_yardi_staged_lease_relationship(run.id, lease_row.id, db, actor)
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["resource_coverage"]["UNITS"]["matched_existing"] == 1
        assert baseline["lease_relationship_readiness"]["complete_identity_links"] == 1
        dry_run_yardi_review(run.id, db, actor)
        db.refresh(run)
        assert run.last_dry_run_fingerprint == baseline["review_fingerprint"]

        # A later conflicting source version is not automatically skipped or
        # reconciled merely because the original Unit is already durably bound.
        upload = stage_yardi_file(
            db, run=run, filename="later-units.csv",
            content=b"Unit,Parent,Label\nU1,P2,101\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "Unit", "source_property_id": "Parent",
                "unit_name": "Label",
            }, platform_user_id=actor.id,
        )
        db.commit()
        duplicate = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        colliding = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert colliding["resource_coverage"]["UNITS"]["matched_existing"] == 0
        assert colliding["resource_coverage"]["UNITS"]["mapped"] == 0
        assert colliding["resource_coverage"]["UNITS"]["needs_review"] == 2
        assert colliding["lease_relationship_readiness"]["complete_identity_links"] == 0
        assert colliding["lease_relationship_readiness"]["identity_source_id_collisions"] == 1
        assert colliding["lease_relationship_readiness"]["accepted_relationship_stale"] == 1
        assert colliding["review_fingerprint"] != baseline["review_fingerprint"]
        lease_preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert lease_preview["relationship_review_current"] is False
        assert "UNIT_SOURCE_ID_COLLISION" in lease_preview["blockers"]
        with pytest.raises(HTTPException) as rejected:
            accept_yardi_staged_lease_relationship(run.id, lease_row.id, db, actor)
        assert rejected.value.status_code == 409

        # Only an explicit reason-coded staff action restores current status;
        # original mapping and customer records remain unchanged.
        skipped = skip_yardi_staged_row(
            run.id, duplicate.id, YardiRowSkipIn(reason_code="DUPLICATE_SOURCE"),
            db, actor,
        )
        assert skipped["action"] == "SKIP"
        restored = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored["resource_coverage"]["UNITS"]["matched_existing"] == 1
        assert restored["resource_coverage"]["UNITS"]["skipped"] == 1
        assert restored["resource_coverage"]["UNITS"]["needs_review"] == 0
        assert restored["lease_relationship_readiness"]["identity_source_id_collisions"] == 0
        assert restored["lease_relationship_readiness"]["complete_identity_links"] == 1
        assert restored["lease_relationship_readiness"]["accepted_relationship_stale"] == 0
        assert list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]["relationship_review_current"] is True
        assert accept_yardi_staged_lease_relationship(
            run.id, lease_row.id, db, actor,
        )["replayed"] is True
        assert db.query(Lease).count() == 0
        db.refresh(unit)
        db.refresh(tenant)
        assert unit.property_id == original.id
        assert tenant.hashed_password == "unchanged-password-hash"
    finally:
        db.close()
        engine.dispose()

def test_yardi_aggregate_review_rejects_wrong_durable_target_entity():
    """Matching numeric ID and fingerprint cannot substitute for entity type."""
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, "yardi-aggregate-typed-durable-link",
        )
        bound = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "UNITS",
        ).one()
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["resource_coverage"]["UNITS"]["matched_existing"] == 1
        assert baseline["resource_coverage"]["UNITS"]["needs_review"] == 0
        bound.target_entity = "PROPERTY"
        db.commit()
        stale = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert stale["resource_coverage"]["UNITS"]["matched_existing"] == 0
        assert stale["resource_coverage"]["UNITS"]["needs_review"] == 1
        assert stale["review_fingerprint"] != baseline["review_fingerprint"]
        assert stale["lease_relationship_readiness"]["complete_identity_links"] == 0
        bound.target_entity = "UNIT"
        db.commit()
        restored = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored["resource_coverage"]["UNITS"]["matched_existing"] == 1
        assert restored["review_fingerprint"] == baseline["review_fingerprint"]
        assert db.query(Lease).count() == 0
        db.refresh(tenant)
        assert tenant.hashed_password == "unchanged-password-hash"
    finally:
        db.close()
        engine.dispose()


def test_accepted_lease_identity_becomes_stale_after_competing_tenant_staff_review():
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, "yardi-lease-conflicting-staff-target",
        )
        assert accept_yardi_staged_lease_relationship(
            run.id, lease_row.id, db, actor,
        )["replayed"] is False
        initial = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert initial["lease_relationship_readiness"]["complete_identity_links"] == 1

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="another-reviewed-tenant", status="DRAFT",
        )
        db.add(other_run)
        db.commit()
        upload = stage_yardi_file(
            db, run=other_run, filename="other-tenants.csv",
            content=b"Resident Ref,Full Name\nT-OTHER,Other Tenant\n",
            resource_override="TENANTS", sheet_name=None,
            explicit_mapping={"source_id": "Resident Ref", "name": "Full Name"},
            platform_user_id=actor.id,
        )
        db.commit()
        competing = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id
        ).one()
        competing.resolution_action = "MATCH_EXISTING"
        competing.resolution_target_tenant_user_id = tenant.id
        db.commit()
        preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert "TENANT_TARGET_REVIEW_COLLISION" in preview["blockers"]
        assert preview["relationship_review_current"] is False
        report = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert report["lease_relationship_readiness"]["complete_identity_links"] == 0
        assert report["lease_relationship_readiness"]["identity_target_review_collisions"] == 1
        assert report["lease_relationship_readiness"]["accepted_relationship_stale"] == 1
        assert report["review_fingerprint"] != initial["review_fingerprint"]
        with pytest.raises(HTTPException) as stale:
            accept_yardi_staged_lease_relationship(run.id, lease_row.id, db, actor)
        assert stale.value.status_code == 409

        competing.resolution_action = None
        competing.resolution_target_tenant_user_id = None
        db.commit()
        assert accept_yardi_staged_lease_relationship(
            run.id, lease_row.id, db, actor,
        )["replayed"] is True
        final = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert final["lease_relationship_readiness"]["complete_identity_links"] == 1

        # Another run can review the SAME tenant source ID without creating a
        # distinct identity claim (matching the Property/Unit/Owner binders).
        competing.source_id = str((lease_row.normalized_data or {}).get("source_tenant_id") or "").strip()
        competing.resolution_action = "MATCH_EXISTING"
        competing.resolution_target_tenant_user_id = tenant.id
        db.commit()
        same_source = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert "TENANT_TARGET_REVIEW_COLLISION" not in same_source["blockers"]
        assert same_source["relationship_review_current"] is True
        assert accept_yardi_staged_lease_relationship(
            run.id, lease_row.id, db, actor,
        )["replayed"] is True

        # Historical NULL-source review must remain a competing claim.
        competing.source_id = None
        db.commit()
        unknown = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert "TENANT_TARGET_REVIEW_COLLISION" in unknown["blockers"]
        assert unknown["relationship_review_current"] is False
        summary = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert summary["lease_relationship_readiness"]["identity_target_review_collisions"] == 1
        assert summary["lease_relationship_readiness"]["complete_identity_links"] == 0
        with pytest.raises(HTTPException) as blocked:
            accept_yardi_staged_lease_relationship(run.id, lease_row.id, db, actor)
        assert blocked.value.status_code == 409
        assert db.query(Lease).count() == 0
        db.refresh(tenant)
        assert tenant.hashed_password == "unchanged-password-hash"
    finally:
        db.close()
        engine.dispose()



def test_yardi_lease_review_fingerprint_changes_when_stale_target_swaps_with_equal_counts():
    """A changed identity claim must invalidate a saved dry run even with equal totals."""
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant1, first_lease = _seed(
            db, "yardi-lease-target-swap-fingerprint",
        )
        tenant2 = User(
            organization_id=org.id, role=UserRole.TENANT,
            email="yardi-second-tenant@example.test",
            hashed_password="unchanged-second-hash",
            first_name="Second", last_name="Resident", is_active=True,
        )
        db.add(tenant2)
        db.flush()
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource="TENANTS", source_id="T2", target_entity="TENANT_USER",
            target_id=tenant2.id, source_fingerprint="reviewed-T2",
        ))
        db.commit()
        uploaded = stage_yardi_file(
            db, run=run, filename="another-lease.csv",
            content=b"Lease,Tenant,Property,Unit\nL2,T2,P1,U1\n",
            resource_override="LEASE_OCCUPANCY", sheet_name=None,
            explicit_mapping={
                "source_id": "Lease", "source_tenant_id": "Tenant",
                "source_property_id": "Property", "source_unit_id": "Unit",
            }, platform_user_id=actor.id,
        )
        db.commit()
        second_lease = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == uploaded.upload.id
        ).one()
        assert accept_yardi_staged_lease_relationship(
            run.id, first_lease.id, db, actor,
        )["replayed"] is False
        assert accept_yardi_staged_lease_relationship(
            run.id, second_lease.id, db, actor,
        )["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["lease_relationship_readiness"]["complete_identity_links"] == 2

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="competing-lease-target-switch", status="DRAFT",
        )
        db.add(other_run)
        db.commit()
        competitor_upload = stage_yardi_file(
            db, run=other_run, filename="other-tenants.csv",
            content=b"Resident Ref,Full Name\nT-COMP,Competing Tenant\n",
            resource_override="TENANTS", sheet_name=None,
            explicit_mapping={"source_id": "Resident Ref", "name": "Full Name"},
            platform_user_id=actor.id,
        )
        db.commit()
        competitor = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == competitor_upload.upload.id
        ).one()
        competitor.resolution_action = "MATCH_EXISTING"
        competitor.resolution_target_tenant_user_id = tenant1.id
        db.commit()
        first_conflict = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert first_conflict["lease_relationship_readiness"]["complete_identity_links"] == 1
        assert first_conflict["lease_relationship_readiness"]["accepted_relationship_stale"] == 1
        assert first_conflict["lease_relationship_readiness"]["identity_target_review_collisions"] == 1

        competitor.resolution_target_tenant_user_id = tenant2.id
        db.commit()
        swapped = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert swapped["lease_relationship_readiness"] == first_conflict["lease_relationship_readiness"]
        assert swapped["resource_coverage"] == first_conflict["resource_coverage"]
        assert swapped["review_fingerprint"] != first_conflict["review_fingerprint"]

        # Historical unknown-source reviewed evidence must still contest the
        # target in both read-only Lease views after batching the claim lookup.
        competitor.source_id = None
        db.commit()
        unknown = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert unknown["lease_relationship_readiness"]["identity_target_review_collisions"] == 1
        assert unknown["lease_relationship_readiness"]["accepted_relationship_stale"] == 1
        assert unknown["lease_relationship_readiness"]["complete_identity_links"] == 1
        preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )
        assert sum(
            "TENANT_TARGET_REVIEW_COLLISION" in row["blockers"]
            for row in preview["items"]
        ) == 1
        assert next(
            row for row in preview["items"] if row["source_id"] == "L2"
        )["relationship_review_current"] is False

        # A second reviewable Lease must not add per-row target-claim SELECTs.
        def select_count(fn):
            statements = []
            def observe(connection, cursor, statement, parameters, context, executemany):
                if statement.lstrip().upper().startswith("SELECT"):
                    statements.append(statement)
            event.listen(engine, "before_cursor_execute", observe)
            try:
                fn()
            finally:
                event.remove(engine, "before_cursor_execute", observe)
            return len(statements)

        def summarize():
            return get_yardi_reconciliation(run.id, Response(), db, actor)

        def preview_rows():
            return list_yardi_lease_relationships(
                run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
            )

        # Warm ORM state consistently so expiration after commit does not
        # masquerade as a per-Lease SQL query-count regression.
        summarize()
        preview_rows()
        with_two_summary = select_count(summarize)
        with_two_preview = select_count(preview_rows)
        second_lease.resolution_action = "SKIP"
        db.commit()
        summarize()
        preview_rows()
        assert select_count(summarize) == with_two_summary
        assert select_count(preview_rows) == with_two_preview
        assert db.query(Lease).count() == 0
        db.refresh(tenant1)
        db.refresh(tenant2)
        assert tenant1.hashed_password == "unchanged-password-hash"
        assert tenant2.hashed_password == "unchanged-second-hash"
    finally:
        db.close()
        engine.dispose()



@pytest.mark.parametrize("resource,source_id,entity", [
    ("PROPERTIES", "P1", "PROPERTY"),
    ("UNITS", "U1", "UNIT"),
    ("TENANTS", "T1", "TENANT_USER"),
])
@pytest.mark.parametrize("direction", ["different_source_same_target", "same_source_different_target"])
def test_yardi_accepted_lease_revalidates_cross_run_durable_identity_claims(
    resource, source_id, entity, direction,
):
    """Both durable-claim directions invalidate acceptance, preview and dry-run."""
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, "yardi-lease-durable-claims-" + resource.lower() + "-" + direction,
        )
        assert accept_yardi_staged_lease_relationship(
            run.id, lease_row.id, db, actor,
        )["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["lease_relationship_readiness"]["complete_identity_links"] == 1
        selected = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == resource,
            PlatformMigrationItem.source_id == source_id,
        ).one()
        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="historical-durable-identity", status="DRAFT",
        )
        db.add(other_run)
        db.flush()
        if direction == "different_source_same_target":
            contender_source = "OTHER-" + source_id
            contender_target = selected.target_id
        else:
            contender_source = source_id
            if resource == "PROPERTIES":
                contender_target = alternate.id
            elif resource == "UNITS":
                second_unit = Unit(property_id=original.id, unit_number="102")
                db.add(second_unit)
                db.flush()
                contender_target = second_unit.id
            else:
                second_tenant = User(
                    organization_id=org.id, role=UserRole.TENANT,
                    email="second-" + resource.lower() + "-" + direction + "@example.test",
                    hashed_password="preserved-second-hash",
                    first_name="Second", last_name="Tenant", is_active=True,
                )
                db.add(second_tenant)
                db.flush()
                contender_target = second_tenant.id
        competitor = PlatformMigrationItem(
            run_id=other_run.id, organization_id=org.id, provider="YARDI",
            resource=resource, source_id=contender_source,
            target_entity=entity, target_id=contender_target,
            source_fingerprint="historical-staff-reviewed",
        )
        db.add(competitor)
        db.commit()
        preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        kind = {"PROPERTIES": "PROPERTY", "UNITS": "UNIT", "TENANTS": "TENANT"}[resource]
        expected = (
            kind + "_TARGET_BINDING_COLLISION"
            if direction == "different_source_same_target"
            else kind + "_SOURCE_BINDING_COLLISION"
        )
        assert expected in preview["blockers"]
        assert preview["relationship_review_recorded"] is True
        assert preview["relationship_review_current"] is False
        assert preview["occupancy_or_lease_authorized"] is False
        summary = get_yardi_reconciliation(run.id, Response(), db, actor)
        coverage = summary["lease_relationship_readiness"]
        assert coverage["complete_identity_links"] == 0
        assert coverage["accepted_relationship_stale"] == 1
        count_key = (
            "identity_target_binding_collisions"
            if direction == "different_source_same_target"
            else "identity_source_binding_collisions"
        )
        assert coverage[count_key] == 1
        assert summary["review_fingerprint"] != baseline["review_fingerprint"]
        with pytest.raises(HTTPException) as stale:
            accept_yardi_staged_lease_relationship(run.id, lease_row.id, db, actor)
        assert stale.value.status_code == 409
        db.refresh(lease_row)
        assert lease_row.resolution_action == "ACCEPT_RELATIONSHIP"
        # Converging the exact historical source/target resolves ambiguity;
        # the system never changes or merges either customer's business data.
        if direction == "different_source_same_target":
            competitor.source_id = source_id
        else:
            competitor.target_id = selected.target_id
        db.commit()
        restored = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert expected not in restored["blockers"]
        assert restored["relationship_review_current"] is True
        healthy = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert healthy["lease_relationship_readiness"]["complete_identity_links"] == 1
        assert healthy["review_fingerprint"] != summary["review_fingerprint"]
        assert accept_yardi_staged_lease_relationship(
            run.id, lease_row.id, db, actor,
        )["replayed"] is True
        assert db.query(Lease).count() == 0
        db.refresh(original)
        db.refresh(unit)
        db.refresh(tenant)
        assert original.name == "Original"
        assert unit.unit_number == "101"
        assert tenant.hashed_password == "unchanged-password-hash"
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("scope", ["other_organization", "other_provider"])
def test_yardi_lease_durable_claim_projection_respects_provider_and_organization(scope):
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, "yardi-lease-durable-claim-boundary-" + scope,
        )
        if scope == "other_organization":
            other_org = _org(db, "yardi-lease-foreign-claim-" + scope)
            other_org_id, provider = other_org.id, "YARDI"
        else:
            other_org_id, provider = org.id, "APPFOLIO"
        other_run = PlatformMigrationRun(
            organization_id=other_org_id, provider=provider,
            source_account_ref="foreign-provider-or-org", status="DRAFT",
        )
        db.add(other_run)
        db.flush()
        db.add(PlatformMigrationItem(
            run_id=other_run.id, organization_id=other_org_id,
            provider=provider, resource="TENANTS", source_id="FOREIGN",
            target_entity="TENANT_USER", target_id=tenant.id,
            source_fingerprint="unrelated-provider-source",
        ))
        db.commit()
        preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert "TENANT_TARGET_BINDING_COLLISION" not in preview["blockers"]
        assert preview["identity_links_complete"] is True
        assert get_yardi_reconciliation(
            run.id, Response(), db, actor,
        )["lease_relationship_readiness"]["complete_identity_links"] == 1
        assert accept_yardi_staged_lease_relationship(
            run.id, lease_row.id, db, actor,
        )["replayed"] is False
        assert db.query(Lease).count() == 0
        db.refresh(tenant)
        assert tenant.hashed_password == "unchanged-password-hash"
    finally:
        db.close()
        engine.dispose()
