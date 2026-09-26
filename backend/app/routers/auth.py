# ============================================================
# routers/auth.py
# ------------------------------------------------------------
# HTTP routes for authentication:
#
#   POST /auth/signup  -> register a new user
#   POST /auth/login   -> get a JWT token
#   GET  /auth/me      -> get the logged-in user's info
#
# These routes use the logic from app/core/auth.py.
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core import auth as auth_logic
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_two_factor_challenge_token,
    decode_access_token,
    decode_two_factor_challenge_token,
)
from app.models.user import User
from app.schemas.auth import LoginRequest
from app.schemas.two_factor import TwoFactorLoginVerifyRequest
from app.schemas.token import LoginResponse
from app.schemas.user import UserCreate, UserOut
from app.services.login_history import record_login_event
from app.services.auto_audit import bind_customer_audit_actor
from app.services.two_factor import get_settings as get_two_factor_settings, verify_login_code


router = APIRouter(prefix="/auth", tags=["Authentication"])

# This tells FastAPI where clients should send username/password.
# It also powers the "Authorize" button in the /docs page.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ------------------------------------------------------------
# DEPENDENCY: get the current logged-in user
# ------------------------------------------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Read the JWT from the Authorization header,
    decode it, and return the matching User.
    Raises 401 if the token is invalid or the user doesn't exist.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if not payload:
        raise credentials_error

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_error

    user = auth_logic.get_user_by_id(db, int(user_id))
    if user is None:
        raise credentials_error

    bind_customer_audit_actor(db, user)
    return user


# ------------------------------------------------------------
# POST /auth/signup
# ------------------------------------------------------------
@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.
    Returns the created user (without the password).
    """
    try:
        user = auth_logic.create_user(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return user


# ------------------------------------------------------------
# POST /auth/login
# ------------------------------------------------------------
@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Verify email + password. Returns a JWT token."""
    candidate = auth_logic.get_user_by_email(db, payload.email)
    user = auth_logic.authenticate_user(db, payload.email, payload.password)
    if not user:
        if candidate is not None:
            record_login_event(db, user=candidate, request=request, success=False, auth_method="PASSWORD", reason="invalid_credentials")
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    two_factor = get_two_factor_settings(db, user.id)
    if two_factor is not None and two_factor.is_enabled:
        return LoginResponse(two_factor_required=True, challenge_token=create_two_factor_challenge_token(user.id))

    record_login_event(db, user=user, request=request, success=True, auth_method="PASSWORD")
    db.commit()
    token = create_access_token(subject=user.id)
    return LoginResponse(access_token=token, token_type="bearer")


@router.post("/two-factor/verify", response_model=LoginResponse)
def verify_two_factor_login(
    payload: TwoFactorLoginVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    challenge = decode_two_factor_challenge_token(payload.challenge_token)
    if not challenge or challenge.get("sub") is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired two-step challenge.")

    user = auth_logic.get_user_by_id(db, int(challenge["sub"]))
    row = get_two_factor_settings(db, user.id) if user is not None else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired two-step challenge.")
    if row is None or not row.is_enabled:
        record_login_event(db, user=user, request=request, success=False, auth_method="TWO_FACTOR", reason="invalid_or_expired_challenge")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired two-step challenge.")

    if not verify_login_code(db, row=row, code=payload.code):
        db.rollback()
        record_login_event(db, user=user, request=request, success=False, auth_method="TWO_FACTOR", reason="invalid_two_factor_code")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification or recovery code.")

    record_login_event(db, user=user, request=request, success=True, auth_method="TWO_FACTOR")
    db.commit()
    return LoginResponse(access_token=create_access_token(subject=user.id), token_type="bearer")


# ------------------------------------------------------------
# GET /auth/me  (protected route)
# ------------------------------------------------------------
@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    """
    Return the currently logged-in user's info.
    Requires a valid JWT in the Authorization header.
    """
    return current_user