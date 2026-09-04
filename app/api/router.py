from fastapi import APIRouter

from app.modules.cats.router import router as cats_router
from app.modules.gacha.router import router as gacha_router
from app.modules.grading.router import router as grading_router
from app.modules.housing.router import router as housing_router
from app.modules.identity.router import router as identity_router
from app.modules.learning.router import router as learning_router
from app.modules.shop.router import router as shop_router

api_router = APIRouter()
api_router.include_router(identity_router)
api_router.include_router(grading_router)
api_router.include_router(learning_router)
api_router.include_router(cats_router)
api_router.include_router(gacha_router)
api_router.include_router(shop_router)
api_router.include_router(housing_router)
