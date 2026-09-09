from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import settings
from app.integrations.ax_platform import (
    PlatformEnrichment,
    PlatformService,
    PlatformUnavailable,
    RoundTeam,
    get_platform_service,
)
from app.models.auth_session import AuthSession
from app.models.user import User
from app.modules.identity.rate_limit import (
    auth_bucket_hash,
    blocked_retry_after,
    lock_rate_buckets,
    record_failed_attempts,
    record_request_attempt,
    reset_rate_bucket,
)
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

Platform = Annotated[PlatformService, Depends(get_platform_service)]


class SessionRead(UserRead):
    platform: PlatformEnrichment


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
def register(payload: RegistrationCommand, request: Request, response: Response, db: DbSession) -> UserRead:
    """Create a password account and issue a new opaque browser session."""
    registration_hash = auth_bucket_hash("register-ip", _client_ip(request))
    buckets = lock_rate_buckets(db, [registration_hash])
    retry_after = blocked_retry_after(
        buckets,
        attempt_limit=settings.auth_registration_attempt_limit,
    )
    if retry_after is not None:
        db.commit()
        raise _rate_limited(retry_after)
    record_request_attempt(buckets)
    existing = db.scalar(select(User.id).where(func.lower(User.email) == payload.email))
    if existing is not None:
        db.commit()
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
        retry_buckets = lock_rate_buckets(db, [registration_hash])
        record_request_attempt(retry_buckets)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="account-already-exists",
        ) from error
    _issue_session(db, response, user)
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.post("/login", response_model=UserRead)
def login(payload: LoginCommand, request: Request, response: Response, db: DbSession) -> UserRead:
    """Verify an Argon2 password and rotate to a newly generated browser session."""
    normalized_email = payload.email.strip().lower()
    account_hash = auth_bucket_hash("login-account", normalized_email)
    ip_hash = auth_bucket_hash("login-ip", _client_ip(request))
    ip_buckets = lock_rate_buckets(db, [ip_hash])
    retry_after = blocked_retry_after(
        ip_buckets,
        attempt_limit=settings.auth_login_attempt_limit,
    )
    if retry_after is not None:
        db.commit()
        raise _rate_limited(retry_after)
    account_buckets = lock_rate_buckets(db, [account_hash])
    retry_after = blocked_retry_after(
        account_buckets,
        attempt_limit=settings.auth_login_attempt_limit,
    )
    if retry_after is not None:
        db.commit()
        raise _rate_limited(retry_after)
    buckets = [*ip_buckets, *account_buckets]
    user = db.scalar(select(User).where(func.lower(User.email) == normalized_email))
    encoded_hash = user.password_hash if user and user.password_hash else DUMMY_PASSWORD_HASH
    if not verify_password(payload.password, encoded_hash) or user is None or user.password_hash is None:
        retry_after = record_failed_attempts(
            buckets,
            attempt_limit=settings.auth_login_attempt_limit,
        )
        db.commit()
        if retry_after is not None:
            raise _rate_limited(retry_after)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid-credentials")
    reset_rate_bucket(account_buckets[0])
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


@router.get("/me", response_model=SessionRead)
def current_session(user: CurrentUser, platform: Platform) -> SessionRead:
    """Return the public profile resolved by the active authentication adapter."""
    return SessionRead(
        **UserRead.model_validate(user).model_dump(),
        platform=platform.enrich(user.homepage_user_id),
    )


@router.get("/me/round-teams", response_model=list[RoundTeam])
def current_round_teams(
    user: CurrentUser,
    platform: Platform,
    round_id: Annotated[int | None, Query(ge=1, le=9_223_372_036_854_775_807)] = None,
) -> list[RoundTeam]:
    """Read only the authenticated user's AX2 history, optionally for an AX2 round."""
    if user.homepage_user_id is None:
        raise HTTPException(status_code=404, detail="ax-platform-user-unlinked")
    try:
        return platform.round_teams(user.homepage_user_id, round_id)
    except PlatformUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from None


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


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _rate_limited(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="too-many-authentication-attempts",
        headers={"Retry-After": str(retry_after)},
    )
