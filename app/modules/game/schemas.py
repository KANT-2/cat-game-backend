"""Public JSON contracts for the authoritative game snapshot."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class GameSettingsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bgm_enabled: bool = True
    bgm_volume: int = Field(default=70, ge=0, le=100)
    effects_enabled: bool = True
    effects_volume: int = Field(default=80, ge=0, le=100)
    reduced_motion: bool = False


class GameCatRead(BaseModel):
    public_id: uuid.UUID
    catalog_key: str
    name: str
    persona: str
    rarity: str
    owned: bool
    is_home: bool


class GameItemRead(BaseModel):
    public_id: uuid.UUID
    catalog_key: str
    category: str
    name: str
    price: int
    furniture_kind: str | None
    width: int | None
    height: int | None
    owned_quantity: int
    available_quantity: int


class GamePlacementRead(BaseModel):
    public_id: uuid.UUID
    item_catalog_key: str
    x: int
    y: int
    rotation: int = Field(ge=0, le=1)


class GameSnapshotRead(BaseModel):
    catalog_version: int
    state_version: int
    balance: int
    mileage: int
    house_level: int
    active_cat_key: str
    active_wallpaper_key: str | None
    active_floor_key: str | None
    settings: GameSettingsRead
    cats: list[GameCatRead]
    items: list[GameItemRead]
    placements: list[GamePlacementRead]
