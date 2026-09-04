import uuid
from typing import Literal

from pydantic import BaseModel


class SurfaceApplicationRead(BaseModel):
    user_public_id: uuid.UUID
    item_public_id: uuid.UUID
    category: Literal["WALLPAPER", "FLOOR"]