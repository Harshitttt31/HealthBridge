"""Auth (BRD §5, FR-01) — bcrypt passwords + JWT carrying {user_id, role, company_id}.

POST /auth/login verifies credentials and returns a signed token. Downstream
routes depend on `get_current_user` to decode it, and on `require_role(...)` to
enforce that HR can only touch HRMS and Employer only AHC.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlmodel import Session, select

from app.config import get_settings
from app.db import get_session
from app.models import Role, User

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

router = APIRouter(prefix="/auth", tags=["auth"])


# --- password helpers -------------------------------------------------------
# bcrypt directly (passlib is unmaintained and breaks on bcrypt>=4). bcrypt caps
# input at 72 bytes, so we encode and truncate defensively.
def hash_password(plain: str) -> str:
    pw = plain.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    pw = plain.encode("utf-8")[:72]
    return bcrypt.checkpw(pw, hashed.encode("utf-8"))


# --- token helpers ----------------------------------------------------------
def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    claims = {
        "sub": str(user.id),
        "user_id": user.id,
        "role": user.role.value,
        "company_id": user.company_id,
        "exp": expire,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# --- request/response schemas ----------------------------------------------
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    company_id: str


class CurrentUser(BaseModel):
    user_id: int
    role: Role
    company_id: str


# --- dependencies -----------------------------------------------------------
def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    """Decode the bearer token into the caller's identity, or 401."""
    cred_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("user_id")
        role = payload.get("role")
        company_id = payload.get("company_id")
        if user_id is None or role is None or company_id is None:
            raise cred_error
        return CurrentUser(user_id=user_id, role=Role(role), company_id=company_id)
    except (JWTError, ValueError):
        raise cred_error


def require_role(required: Role):
    """Dependency factory: 403 unless the caller holds the given role."""

    def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role != required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role '{required.value}'",
            )
        return user

    return checker


# --- routes -----------------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    user = session.exec(select(User).where(User.email == body.email)).first()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return TokenResponse(
        access_token=create_access_token(user),
        role=user.role,
        company_id=user.company_id,
    )


@router.get("/me", response_model=CurrentUser)
def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Echo the caller's identity — useful for the frontend to confirm a session."""
    return user
