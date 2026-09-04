"""Shared FastAPI dependencies only; domain dependencies stay in their modules."""

import uuid
from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User


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


async def get_current_user(
    request: Request,
    db: DbSession,
    user_public_id: Annotated[uuid.UUID | None, Header(alias="X-User-Public-ID")] = None,
) -> User:
    """Validate the Django session through the host bridge and JIT-provision a game user."""
    if settings.app_env in {"local", "test"} and user_public_id is not None:
        user = db.scalar(select(User).where(User.public_id == user_public_id))
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Development user was not found")
        return user
    if not settings.ax_auth_base_url:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Host authentication is not configured"
        )
    session_cookie = request.cookies.get(settings.ax_auth_session_cookie_name)
    if not session_cookie:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    url = settings.ax_auth_base_url.rstrip("/") + "/" + settings.ax_auth_me_path.lstrip("/")
    try:
        async with httpx.AsyncClient(timeout=settings.ax_auth_timeout_seconds) as client:
            response = await client.get(
                url,
                cookies={settings.ax_auth_session_cookie_name: session_cookie},
                headers={"Accept": "application/json"},
            )
        if response.status_code in {401, 403}:
            raise HTTPException(response.status_code, "Host account is not authorized")
        response.raise_for_status()
        payload = response.json()
        if "display_name" not in payload:
            payload["display_name"] = payload.get("name") or payload.get("first_name") or "Player"
        host_user = HostUser.model_validate(payload)
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, ValidationError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Host authentication is temporarily unavailable"
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
    db.commit()
    db.refresh(user)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
