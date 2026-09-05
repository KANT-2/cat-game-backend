from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, DbSession
from app.modules.game.bootstrap import GameCatalogNotSeededError
from app.modules.game.schemas import GameSnapshotRead
from app.modules.game.service import get_game_snapshot

router = APIRouter(prefix="/game", tags=["game"])


@router.get("/snapshot", response_model=GameSnapshotRead)
def game_snapshot(db: DbSession, user: CurrentUser) -> GameSnapshotRead:
    """Return the authenticated player's authoritative game state and catalog."""
    try:
        return get_game_snapshot(db, user)
    except GameCatalogNotSeededError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Game catalog is not initialized",
        ) from error
