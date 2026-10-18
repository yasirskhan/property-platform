"""Provider-specific, nonsecret DoorLoop migration-run input."""
from app.schemas.rentmanager_migration import RentManagerRunCreateIn


class DoorLoopRunCreateIn(RentManagerRunCreateIn):
    """Same validated nonsecret source reference contract as other provider runs."""
