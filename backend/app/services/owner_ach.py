from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.owner_ach import OwnerACHAccount
from app.models.user import User, UserRole
from app.schemas.owner_ach import OwnerACHOut, OwnerACHUpsertIn
from app.services.ach_file import aba_valid


class OwnerACHError(ValueError):
    pass


def _role_value(role) -> str:
    return role.value if hasattr(role, "value") else str(role or "")


def require_owner(
    db: Session,
    *,
    organization_id: int,
    owner_id: int,
) -> User:
    owner = (
        db.query(User)
        .filter(
            User.id == owner_id,
            User.organization_id == organization_id,
            User.is_active.is_(True),
        )
        .first()
    )
    if owner is None or _role_value(owner.role).upper() != UserRole.OWNER.value:
        raise OwnerACHError("Owner not found.")
    return owner


def get_owner_ach(
    db: Session,
    *,
    organization_id: int,
    owner_id: int,
) -> OwnerACHOut:
    require_owner(
        db,
        organization_id=organization_id,
        owner_id=owner_id,
    )
    row = (
        db.query(OwnerACHAccount)
        .filter(
            OwnerACHAccount.organization_id == organization_id,
            OwnerACHAccount.owner_id == owner_id,
        )
        .first()
    )
    if row is None:
        return OwnerACHOut(owner_id=owner_id, configured=False)

    return OwnerACHOut(
        owner_id=owner_id,
        configured=True,
        account_holder_name=row.account_holder_name,
        bank_name=row.bank_name,
        routing_last4=row.routing_number[-4:],
        account_last4=row.account_number[-4:],
        account_type=row.account_type,
        is_enabled=bool(row.is_enabled),
        updated_at=row.updated_at,
    )


def upsert_owner_ach(
    db: Session,
    *,
    organization_id: int,
    owner_id: int,
    payload: OwnerACHUpsertIn,
    actor: User,
) -> OwnerACHOut:
    require_owner(
        db,
        organization_id=organization_id,
        owner_id=owner_id,
    )
    if not aba_valid(payload.routing_number):
        raise OwnerACHError("routing_number must be a valid ABA routing number.")

    row = (
        db.query(OwnerACHAccount)
        .filter(
            OwnerACHAccount.organization_id == organization_id,
            OwnerACHAccount.owner_id == owner_id,
        )
        .first()
    )
    if row is None:
        row = OwnerACHAccount(
            organization_id=organization_id,
            owner_id=owner_id,
            created_by_id=actor.id,
        )
        db.add(row)

    row.account_holder_name = payload.account_holder_name.strip()
    row.bank_name = payload.bank_name.strip() if payload.bank_name else None
    row.routing_number = payload.routing_number
    row.account_number = payload.account_number
    row.account_type = payload.account_type
    row.is_enabled = payload.is_enabled
    row.updated_by_id = actor.id

    db.commit()
    db.refresh(row)
    return get_owner_ach(
        db,
        organization_id=organization_id,
        owner_id=owner_id,
    )
