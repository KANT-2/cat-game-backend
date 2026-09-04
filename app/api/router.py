from fastapi import APIRouter

from app.modules.grading.router import router as grading_router
from app.modules.identity.router import router as identity_router
from app.modules.learning.router import router as learning_router

api_router = APIRouter()
api_router.include_router(identity_router)
api_router.include_router(grading_router)
api_router.include_router(learning_router)
