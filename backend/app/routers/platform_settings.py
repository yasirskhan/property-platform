# ============================================================
# routers/platform_settings.py
# ------------------------------------------------------------
# Admin-only platform settings (OCR, integrations).
#
#   GET    /platform-settings
#   GET    /platform-settings/ocr
#   PUT    /platform-settings/ocr
# ============================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.ocr import get_ocr_config
from app.models.platform_settings import PlatformSetting
from app.models.user import User, UserRole
from app.routers.auth import get_current_user


router = APIRouter(prefix="/platform-settings", tags=["Platform Settings"])


def _require_admin(current_user: User):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin only")


@router.get("/ocr")
def get_ocr_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    cfg = get_ocr_config(db)
    # Mask secrets when returning
    return {
        "provider": cfg["provider"],
        "mindee_api_key": _mask(cfg["mindee_api_key"]),
        "google_api_key": _mask(cfg["google_api_key"]),
        "aws_access_key": _mask(cfg["aws_access_key"]),
        "aws_secret_key": _mask(cfg["aws_secret_key"]),
        "aws_region": cfg["aws_region"],
        "has_mindee_key": bool(cfg["mindee_api_key"]),
        "has_google_key": bool(cfg["google_api_key"]),
        "has_aws_key": bool(cfg["aws_access_key"]),
    }


@router.put("/ocr")
def update_ocr_settings(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    allowed_keys = {
        "provider",
        "mindee_api_key",
        "google_api_key",
        "aws_access_key",
        "aws_secret_key",
        "aws_region",
    }

    for key, value in payload.items():
        if key not in allowed_keys:
            continue

        setting_key = f"ocr.{key}"
        row = db.query(PlatformSetting).filter(PlatformSetting.key == setting_key).first()
        if row:
            # Only update if value is not an empty placeholder
            if value is not None and value != "" and not str(value).startswith("•••"):
                row.value = str(value)
        else:
            db.add(PlatformSetting(key=setting_key, value=str(value) if value else ""))

    db.commit()
    return {"detail": "OCR settings saved."}


def _mask(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "••••••"
    return value[:3] + "••••" + value[-3:]