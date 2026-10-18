"""Provider-specific, nonsecret DoorLoop migration-run input."""
from app.schemas.rentmanager_migration import RentManagerRunCreateIn, RentManagerRunOut


class DoorLoopRunCreateIn(RentManagerRunCreateIn):
    """Same validated nonsecret source reference contract as other provider runs."""


class DoorLoopRunOut(RentManagerRunOut):
    """Explicit response-field allowlist; never serialize the full ORM model."""
