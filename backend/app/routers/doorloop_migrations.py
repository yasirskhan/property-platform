"""Phase 4.17: DoorLoop provider migration discovery; no import writes."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from app.schemas.rentmanager_migration import RentManagerRunCreateIn
from app.services.audit import append_audit_log
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization
from app.routers.platform_auth import get_current_platform_user

router = APIRouter(prefix="/api/platform/migrations/doorloop", tags=["Platform DoorLoop Migration"])
_ALLOWED = {
    PlatformUserRole.PLATFORM_ADMIN, PlatformUserRole.PLATFORM_TECH,
    PlatformUserRole.PLATFORM_SUPPORT, PlatformUserRole.PLATFORM_DEV,
}


def _authorize(user: PlatformUser) -> None:
    if user.role not in _ALLOWED:
        raise HTTPException(status_code=403, detail="Platform migration access required.")


@router.get("/resource-readiness")
def doorloop_resource_readiness(
    response: Response,
    user: PlatformUser = Depends(get_current_platform_user),
):
    _authorize(user)
    response.headers["Cache-Control"] = "no-store"
    return {
        "provider": "DOORLOOP",
        "source_contract_verified": False,
        "official_api_enabled": False,
        "file_staging_enabled": False,
        "controlled_commit_enabled": False,
        "customer_business_mutation": False,
        "blocker": "DoorLoop resource contracts and customer authorization must be reviewed before migration imports.",
    }


@router.get("/runs")
def list_doorloop_runs(
    response: Response,
    organization_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    user: PlatformUser = Depends(get_current_platform_user),
):
    _authorize(user)
    query = db.query(PlatformMigrationRun).join(
        Organization, Organization.id == PlatformMigrationRun.organization_id,
    ).filter(
        PlatformMigrationRun.provider == "DOORLOOP",
        Organization.is_active.is_(True),
    )
    if organization_id is not None:
        org = db.query(Organization).filter(
            Organization.id == organization_id, Organization.is_active.is_(True),
        ).first()
        if org is None:
            raise HTTPException(status_code=404, detail="Target organization not found.")
        query = query.filter(PlatformMigrationRun.organization_id == organization_id)
    response.headers["Cache-Control"] = "no-store"
    return query.order_by(
        PlatformMigrationRun.created_at.desc(), PlatformMigrationRun.id.desc(),
    ).limit(limit).all()


@router.post("/runs", status_code=status.HTTP_201_CREATED)
def create_doorloop_run(
    payload: RentManagerRunCreateIn,
    db: Session = Depends(get_db),
    user: PlatformUser = Depends(get_current_platform_user),
):
    if user.role not in {PlatformUserRole.PLATFORM_ADMIN, PlatformUserRole.PLATFORM_TECH, PlatformUserRole.PLATFORM_DEV}:
        raise HTTPException(status_code=403, detail="Migration creation requires platform write access.")
    org = db.query(Organization).filter(
        Organization.id == payload.organization_id, Organization.is_active.is_(True),
    ).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Target organization not found.")
    run = PlatformMigrationRun(
        organization_id=org.id, provider="DOORLOOP", source_account_ref=payload.source_account_ref,
        status="DRAFT", created_by_platform_user_id=user.id,
    )
    db.add(run)
    db.flush()
    append_audit_log(
        db, platform_user_id=user.id, organization_id=org.id,
        entity_type="platform_migration_run", entity_id=run.id,
        action="doorloop_migration_run_created",
        new_value={"provider": "DOORLOOP", "status": "DRAFT",
                   "credentials_stored": False, "customer_business_mutation": False},
    )
    db.commit()
    db.refresh(run)
    return run


@router.get("/runs/{run_id}")
def get_doorloop_run(
    run_id: int,
    response: Response,
    db: Session = Depends(get_db),
    user: PlatformUser = Depends(get_current_platform_user),
):
    _authorize(user)
    run = db.query(PlatformMigrationRun).join(
        Organization, Organization.id == PlatformMigrationRun.organization_id,
    ).filter(
        PlatformMigrationRun.id == run_id,
        PlatformMigrationRun.provider == "DOORLOOP",
        Organization.is_active.is_(True),
    ).first()
    if run is None:
        raise HTTPException(status_code=404, detail="DoorLoop migration run not found.")
    response.headers["Cache-Control"] = "no-store"
    return run
