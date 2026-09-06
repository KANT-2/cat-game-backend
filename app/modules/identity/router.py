from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import settings
from app.models.auth_session import AuthSession
from app.models.user import User
from app.modules.identity.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    hash_token,
    new_token,
    verify_password,
)
from app.schemas.user import UserRead

router = APIRouter(prefix="/session", tags=["identity"])

DEV_USER_EMAIL = "player@local.nyang"


class RegistrationCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized.count("@") != 1 or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("invalid email address")
        return normalized

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("username cannot be blank")
        return normalized


class LoginCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegistrationCommand, response: Response, db: DbSession) -> UserRead:
    """Create a password account and issue a new opaque browser session."""
    existing = db.scalar(select(User.id).where(func.lower(User.email) == payload.email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="account-already-exists")
    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password),
        role="STUDENT",
        balance=0,
        mileage=0,
        house_level=1,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="account-already-exists",
        ) from error
    _issue_session(db, response, user)
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.post("/login", response_model=UserRead)
def login(payload: LoginCommand, response: Response, db: DbSession) -> UserRead:
    """Verify an Argon2 password and rotate to a newly generated browser session."""
    normalized_email = payload.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == normalized_email))
    encoded_hash = user.password_hash if user and user.password_hash else DUMMY_PASSWORD_HASH
    if not verify_password(payload.password, encoded_hash) or user is None or user.password_hash is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid-credentials")
    _issue_session(db, response, user)
    db.commit()
    return UserRead.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbSession, user: CurrentUser) -> None:
    """Revoke the current opaque session and expire both browser cookies."""
    auth_session = getattr(request.state, "auth_session", None)
    if auth_session is not None:
        auth_session.revoked_at = datetime.now(UTC)
        db.commit()
    response.delete_cookie(settings.session_cookie_name(), path="/")
    response.delete_cookie("nyang_csrf", path="/")


@router.get("/me", response_model=UserRead)
def current_session(user: CurrentUser) -> UserRead:
    """Return the public profile resolved by the active authentication adapter."""
    return UserRead.model_validate(user)


@router.post("/development", response_model=UserRead)
def development_session(db: DbSession) -> UserRead:
    """Create or reuse the local browser integration user.

    This endpoint deliberately disappears outside local and test environments. Production
    deployments must replace the development header with the host authentication provider.
    """
    if settings.app_env not in {"local", "test"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    user = db.scalar(select(User).where(func.lower(User.email) == DEV_USER_EMAIL))
    if user is None:
        user = User(
            email=DEV_USER_EMAIL,
            username="{ 냥 } 플레이어",
            role="STUDENT",
            balance=1_100_000,
            mileage=0,
            house_level=1,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return UserRead.model_validate(user)


def _issue_session(db: DbSession, response: Response, user: User) -> None:
    session_token = new_token()
    csrf_token = new_token()
    max_age = settings.session_days * 24 * 60 * 60
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_token(session_token),
            csrf_token_hash=hash_token(csrf_token),
            expires_at=datetime.now(UTC) + timedelta(seconds=max_age),
        )
    )
    secure = settings.app_env == "production"
    response.set_cookie(
        settings.session_cookie_name(),
        session_token,
        max_age=max_age,
        secure=secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        "nyang_csrf",
        csrf_token,
        max_age=max_age,
        secure=secure,
        httponly=False,
        samesite="lax",
        path="/",
    )
