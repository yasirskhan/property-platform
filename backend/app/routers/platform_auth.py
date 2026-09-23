"""Internal platform authentication routes and dependency."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.platform_auth import authenticate_platform_user, get_platform_user_by_id
from app.core.security import create_platform_access_token, decode_platform_access_token
from app.models.platform_user import PlatformUser
from app.schemas.platform_control import PlatformLoginRequest, PlatformUserOut
from app.schemas.token import Token


router = APIRouter(prefix="/api/platform/auth", tags=["Platform Authentication"])
platform_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/platform/auth/login")


def get_current_platform_user(
    token: str = Depends(platform_oauth2_scheme),
    db: Session = Depends(get_db),
) -> PlatformUser:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate platform credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_platform_access_token(token)
    if not payload:
        raise credentials_error

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise credentials_error

    user = get_platform_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


@router.post("/login", response_model=Token)
def platform_login(
    payload: PlatformLoginRequest,
    db: Session = Depends(get_db),
) -> Token:
    user = authenticate_platform_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect platform email or password",
        )
    return Token(
        access_token=create_platform_access_token(user.id),
        token_type="bearer",
    )


@router.get("/me", response_model=PlatformUserOut)
def platform_me(
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> PlatformUser:
    return current_user
