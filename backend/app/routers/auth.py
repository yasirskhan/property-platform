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

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core import auth as auth_logic
from app.core.database import get_db
from app.core.security import create_access_token, decode_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserOut


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
@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Verify email + password. Returns a JWT token.
    """
    user = auth_logic.authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(subject=user.id)
    return Token(access_token=token, token_type="bearer")


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