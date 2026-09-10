"""Shared FastAPI dependencies only; domain dependencies stay in their modules."""

import uuid
from datetime import UTC, datetime
from hmac import compare_digest
from typing import Annotated

import httpx
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auth_session import AuthSession
from app.models.user import User
from app.modules.identity.security import hash_token


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]


class HostUser(BaseModel):
    id: int
    display_name: str
    role: str
    email: str | None = None
    profile_image: str | None = None


def get_current_user(
    request: Request,
    db: DbSession,
    user_public_id: Annotated[uuid.UUID | None, Header(alias="X-User-Public-ID")] = None,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    local_session: Annotated[str | None, Cookie(alias="nyang_session")] = None,
    production_session: Annotated[str | None, Cookie(alias="__Host-nyang_session")] = None,
) -> User | None:
    """Resolve local header auth or a first-party revocable browser session."""
    if user_public_id is not None and settings.app_env not in {"local", "test"}:
        raise _unauthorized()
    if user_public_id is not None:
        user = db.scalar(select(User).where(User.public_id == user_public_id))
        if user is None:
            raise _unauthorized()
        request.state.auth_session = None
        return user

    raw_session = production_session if settings.app_env == "production" else local_session
    if raw_session is None:
        return None
    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_token(raw_session),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    if auth_session is None:
        raise _unauthorized()
    if request.method not in {"GET", "HEAD", "OPTIONS"} and (
        csrf_token is None
        or not compare_digest(hash_token(csrf_token), auth_session.csrf_token_hash)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf-validation-failed")
    user = db.get(User, auth_session.user_id)
    if user is None:
        raise _unauthorized()
    request.state.auth_session = auth_session
    return user


LocalUser = Annotated[User | None, Depends(get_current_user)]


async def resolve_current_user(
    request: Request,
    db: DbSession,
    local_user: LocalUser,
) -> User:
    """Prefer first-party auth, then validate the configured host session bridge."""
    if local_user is not None:
        request.state.host_user = None
        return local_user
    session_cookie = request.cookies.get(settings.ax_auth_session_cookie_name)
    if not session_cookie:
        raise _unauthorized()
    if not settings.ax_auth_base_url:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Host authentication is not configured",
        )
    url = settings.ax_auth_base_url.rstrip("/") + "/" + settings.ax_auth_me_path.lstrip("/")
    try:
        async with httpx.AsyncClient(timeout=settings.ax_auth_timeout_seconds) as client:
            response = await client.get(
                url,
                cookies={settings.ax_auth_session_cookie_name: session_cookie},
                headers={"Accept": "application/json"},
            )
        if response.status_code in {401, 403} or 300 <= response.status_code < 400:
            raise _unauthorized()
        response.raise_for_status()
        payload = response.json()
        if "display_name" not in payload:
            payload["display_name"] = payload.get("name") or payload.get("first_name") or "Player"
        host_user = HostUser.model_validate(payload)
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, ValidationError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Host authentication is temporarily unavailable",
        ) from exc

    user = db.scalar(select(User).where(User.homepage_user_id == host_user.id))
    normalized_role = host_user.role.upper()
    if user is None:
        user = User(
            homepage_user_id=host_user.id,
            email=host_user.email or f"host-{host_user.id}@invalid.local",
            username=host_user.display_name,
            role=normalized_role,
        )
        db.add(user)
    else:
        user.username = host_user.display_name
        user.role = normalized_role
        if host_user.email:
            user.email = host_user.email
    request.state.auth_session = None
    request.state.host_user = host_user
    db.commit()
    db.refresh(user)
    return user


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication-required")


CurrentUser = Annotated[User, Depends(resolve_current_user)]

def verify_tasks_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """Restrict task-authoring endpoints to holders of the shared team key."""
    expected = settings.tasks_api_key
    if expected is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Tasks API key is not configured"
        )
    if x_api_key is None or not compare_digest(x_api_key, expected.get_secret_value()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid-api-key")


TeamKeyAuth = Annotated[None, Depends(verify_tasks_api_key)]
