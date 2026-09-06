import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.core.exceptions import (
    AlreadyClaimedError,
    ApplicationError,
    IdempotencyConflictError,
    InsufficientBalanceError,
    InvalidItemCategoryError,
    InvalidQuantityError,
    PlacementLimitExceededError,
    PlacementOccupiedError,
    PlacementOutsideRoomError,
    ResourceNotFoundError,
    RewardNotReadyError,
)
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.models.cat import Cat
from app.models.item import Item
from app.models.user import User
from app.modules.game.bootstrap import GameCatalogNotSeededError
from app.modules.game.commands import (
    claim_attendance,
    claim_daily_reward,
    clear_cat_memories,
    reset_learning_progress,
    select_active_cat,
    set_cat_home,
    update_game_settings,
)
from app.modules.game.gacha import draw_game_gacha
from app.modules.game.schemas import (
    CatHomeCommand,
    ConsumableCommand,
    DailyRewardCommand,
    GachaCommand,
    GameMutationRead,
    GameSnapshotRead,
    MovePlacementCommand,
    PlacementCommand,
    PurchaseCommand,
    SettingsCommand,
    ThemeCommand,
)
from app.modules.game.service import get_game_snapshot
from app.modules.housing.service import (
    apply_surface_item,
    place_furniture,
    remove_furniture_placement,
    update_furniture_placement,
)
from app.modules.shop.consumables import use_consumable
from app.modules.shop.service import purchase_item
from app.schemas.placed_object import PositionData

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


@router.post("/shop/purchases", response_model=GameMutationRead)
def buy_item(payload: PurchaseCommand, db: DbSession, user: CurrentUser) -> GameMutationRead:
    """Purchase a catalog item once under the supplied request UUID."""
    item = _catalog_item(db, payload.item_catalog_key)
    try:
        result = purchase_item(
            unit_of_work=SqlAlchemyUnitOfWork(),
            user_public_id=user.public_id,
            request_id=payload.request_id,
            item_public_id=item.public_id,
            quantity=payload.quantity,
        )
        return GameMutationRead(snapshot=_fresh_snapshot(db, user), result=result)
    except ApplicationError as error:
        raise _http_error(error) from error


@router.post("/consumables/use", response_model=GameMutationRead)
def consume_item(payload: ConsumableCommand, db: DbSession, user: CurrentUser) -> GameMutationRead:
    """Consume one owned care item and return the authoritative remaining quantity."""
    item = _catalog_item(db, payload.item_catalog_key)
    cat = _catalog_cat(db, payload.cat_catalog_key)
    try:
        result = use_consumable(
            unit_of_work=SqlAlchemyUnitOfWork(),
            user_public_id=user.public_id,
            request_id=payload.request_id,
            item_public_id=item.public_id,
            cat_public_id=cat.public_id,
        )
        return GameMutationRead(snapshot=_fresh_snapshot(db, user), result=result)
    except ApplicationError as error:
        raise _http_error(error) from error


@router.post("/gacha", response_model=GameMutationRead)
def draw_gacha(payload: GachaCommand, db: DbSession, user: CurrentUser) -> GameMutationRead:
    """Run an idempotent one- or eleven-reward game draw."""
    try:
        result = draw_game_gacha(
            unit_of_work=SqlAlchemyUnitOfWork(),
            user_public_id=user.public_id,
            request_id=payload.request_id,
            draw_count=payload.draw_count,
        )
        return GameMutationRead(snapshot=_fresh_snapshot(db, user), result=result)
    except ApplicationError as error:
        raise _http_error(error) from error


@router.post("/placements", response_model=GameMutationRead)
def add_placement(
    payload: PlacementCommand,
    db: DbSession,
    user: CurrentUser,
) -> GameMutationRead:
    """Place one owned furniture item on the authoritative grid."""
    item = _catalog_item(db, payload.item_catalog_key)
    try:
        placed = place_furniture(
            unit_of_work=SqlAlchemyUnitOfWork(),
            user_public_id=user.public_id,
            item_public_id=item.public_id,
            placement_public_id=payload.placement_public_id,
            position_data=PositionData(x=payload.x, y=payload.y, z=payload.rotation),
        )
        return GameMutationRead(
            snapshot=_fresh_snapshot(db, user),
            result={"placement_public_id": str(placed.public_id)},
        )
    except ApplicationError as error:
        raise _http_error(error) from error


@router.patch("/placements/{placement_public_id}", response_model=GameMutationRead)
def move_placement(
    placement_public_id: uuid.UUID,
    payload: MovePlacementCommand,
    db: DbSession,
    user: CurrentUser,
) -> GameMutationRead:
    """Move one owned placement after authoritative bounds and collision checks."""
    try:
        placed = update_furniture_placement(
            unit_of_work=SqlAlchemyUnitOfWork(),
            user_public_id=user.public_id,
            placed_object_public_id=placement_public_id,
            position_data=PositionData(x=payload.x, y=payload.y, z=payload.rotation),
        )
        return GameMutationRead(
            snapshot=_fresh_snapshot(db, user),
            result={"placement_public_id": str(placed.public_id)},
        )
    except ApplicationError as error:
        raise _http_error(error) from error


@router.delete("/placements/{placement_public_id}", response_model=GameMutationRead)
def delete_placement(
    placement_public_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> GameMutationRead:
    """Remove one owned placement without deleting its inventory entitlement."""
    try:
        remove_furniture_placement(
            unit_of_work=SqlAlchemyUnitOfWork(),
            user_public_id=user.public_id,
            placed_object_public_id=placement_public_id,
        )
        return GameMutationRead(snapshot=_fresh_snapshot(db, user))
    except ApplicationError as error:
        raise _http_error(error) from error


@router.post("/themes", response_model=GameMutationRead)
def apply_theme(payload: ThemeCommand, db: DbSession, user: CurrentUser) -> GameMutationRead:
    """Apply an owned wallpaper or floor catalog item."""
    item = _catalog_item(db, payload.item_catalog_key)
    try:
        applied = apply_surface_item(
            unit_of_work=SqlAlchemyUnitOfWork(),
            user_public_id=user.public_id,
            item_public_id=item.public_id,
        )
        return GameMutationRead(
            snapshot=_fresh_snapshot(db, user),
            result={"item_catalog_key": payload.item_catalog_key, "category": applied.category},
        )
    except ApplicationError as error:
        raise _http_error(error) from error


@router.post("/cats/{catalog_key}/select", response_model=GameMutationRead)
def select_cat(catalog_key: str, db: DbSession, user: CurrentUser) -> GameMutationRead:
    """Select one owned catalog cat as the active companion."""
    try:
        select_active_cat(db, user, catalog_key)
        return GameMutationRead(snapshot=_fresh_snapshot(db, user))
    except ApplicationError as error:
        db.rollback()
        raise _http_error(error) from error


@router.put("/cats/{catalog_key}/home", response_model=GameMutationRead)
def change_cat_home(
    catalog_key: str,
    payload: CatHomeCommand,
    db: DbSession,
    user: CurrentUser,
) -> GameMutationRead:
    """Show or hide one owned catalog cat in the outdoor home scene."""
    try:
        set_cat_home(db, user, catalog_key, visible=payload.visible)
        return GameMutationRead(snapshot=_fresh_snapshot(db, user))
    except ApplicationError as error:
        db.rollback()
        raise _http_error(error) from error


@router.patch("/settings", response_model=GameMutationRead)
def change_settings(
    payload: SettingsCommand,
    db: DbSession,
    user: CurrentUser,
) -> GameMutationRead:
    """Merge a validated settings patch into the authenticated player's state."""
    aliases = {
        "bgm_enabled": "bgmEnabled",
        "bgm_volume": "bgmVolume",
        "effects_enabled": "effectsEnabled",
        "effects_volume": "effectsVolume",
        "reduced_motion": "reducedMotion",
    }
    patch = {
        aliases[key]: value
        for key, value in payload.model_dump(exclude_none=True).items()
    }
    try:
        update_game_settings(db, user, patch)
        return GameMutationRead(snapshot=_fresh_snapshot(db, user))
    except ApplicationError as error:
        db.rollback()
        raise _http_error(error) from error


@router.post("/attendance/claims", response_model=GameMutationRead)
def claim_daily_attendance(db: DbSession, user: CurrentUser) -> GameMutationRead:
    """Claim today's UTC attendance reward once and return the resulting state."""
    try:
        result = claim_attendance(db, user)
        return GameMutationRead(snapshot=_fresh_snapshot(db, user), result=result)
    except ApplicationError as error:
        db.rollback()
        raise _http_error(error) from error


@router.post("/daily-rewards/claims", response_model=GameMutationRead)
def claim_daily_quest_reward(
    payload: DailyRewardCommand,
    db: DbSession,
    user: CurrentUser,
) -> GameMutationRead:
    """Claim one server-validated UTC daily quest or completion bonus reward."""
    try:
        result = claim_daily_reward(db, user, payload.reward_key)
        return GameMutationRead(snapshot=_fresh_snapshot(db, user), result=result)
    except ApplicationError as error:
        db.rollback()
        raise _http_error(error) from error


@router.post("/learning/reset", response_model=GameMutationRead)
def reset_player_learning(db: DbSession, user: CurrentUser) -> GameMutationRead:
    """Clear learning progress while preserving inventory, cats, rewards, and attendance claims."""
    try:
        result = reset_learning_progress(db, user)
        return GameMutationRead(snapshot=_fresh_snapshot(db, user), result=result)
    except ApplicationError as error:
        db.rollback()
        raise _http_error(error) from error


@router.delete("/cat-memories", response_model=GameMutationRead)
def clear_player_cat_memories(db: DbSession, user: CurrentUser) -> GameMutationRead:
    """Delete every stored memory associated with the authenticated user's cats."""
    try:
        result = clear_cat_memories(db, user)
        return GameMutationRead(snapshot=_fresh_snapshot(db, user), result=result)
    except ApplicationError as error:
        db.rollback()
        raise _http_error(error) from error


def _catalog_item(db: DbSession, catalog_key: str) -> Item:
    item = db.scalar(select(Item).where(Item.catalog_key == catalog_key))
    if item is None:
        raise HTTPException(status_code=404, detail="item-not-found")
    return item


def _catalog_cat(db: DbSession, catalog_key: str) -> Cat:
    cat = db.scalar(select(Cat).where(Cat.catalog_key == catalog_key))
    if cat is None:
        raise HTTPException(status_code=404, detail="cat-not-found")
    return cat


def _fresh_snapshot(db: DbSession, user: User) -> GameSnapshotRead:
    db.expire_all()
    refreshed = db.scalar(select(User).where(User.id == user.id))
    if refreshed is None:
        raise HTTPException(status_code=404, detail="user-not-found")
    return get_game_snapshot(db, refreshed)


def _http_error(error: ApplicationError) -> HTTPException:
    if isinstance(error, AlreadyClaimedError):
        return HTTPException(status_code=409, detail="already-claimed")
    if isinstance(error, RewardNotReadyError):
        return HTTPException(status_code=409, detail="reward-not-ready")
    if isinstance(error, ResourceNotFoundError):
        return HTTPException(status_code=404, detail="resource-not-found")
    if isinstance(error, InsufficientBalanceError):
        return HTTPException(status_code=409, detail="insufficient-coins")
    if isinstance(error, IdempotencyConflictError):
        return HTTPException(status_code=409, detail="idempotency-conflict")
    if isinstance(error, PlacementOccupiedError):
        return HTTPException(status_code=409, detail="occupied")
    if isinstance(error, PlacementOutsideRoomError):
        return HTTPException(status_code=422, detail="outside-room")
    if isinstance(error, PlacementLimitExceededError):
        return HTTPException(status_code=409, detail="not-owned")
    if isinstance(error, InvalidItemCategoryError):
        return HTTPException(status_code=422, detail="invalid-item-category")
    if isinstance(error, InvalidQuantityError):
        return HTTPException(status_code=422, detail="invalid-quantity")
    return HTTPException(status_code=500, detail="game-command-failed")
