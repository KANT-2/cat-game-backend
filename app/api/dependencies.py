"""Shared FastAPI dependencies only; domain dependencies stay in their modules."""

import uuid
from datetime import UTC, datetime
from hmac import compare_digest
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
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


def get_current_user(
    request: Request,
    db: DbSession,
    user_public_id: Annotated[uuid.UUID | None, Header(alias="X-User-Public-ID")] = None,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    local_session: Annotated[str | None, Cookie(alias="nyang_session")] = None,
    production_session: Annotated[str | None, Cookie(alias="__Host-nyang_session")] = None,
) -> User:
    """Resolve local header auth or a revocable opaque browser session."""
    if settings.app_env in {"local", "test"} and user_public_id is not None:
        user = db.scalar(select(User).where(User.public_id == user_public_id))
        if user is None:
            raise _unauthorized()
        request.state.auth_session = None
        return user

    raw_session = production_session if settings.app_env == "production" else local_session
    if raw_session is None:
        raise _unauthorized()
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


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication-required")


CurrentUser = Annotated[User, Depends(get_current_user)]
