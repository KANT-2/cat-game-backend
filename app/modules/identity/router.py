from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import settings
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/session", tags=["identity"])

DEV_USER_EMAIL = "player@local.nyang"


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
