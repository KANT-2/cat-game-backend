from fastapi import APIRouter

from app.modules.grading.router import router as grading_router
from app.modules.learning.router import router as learning_router
from app.modules.tasks.router import router as tasks_router

api_router = APIRouter()
api_router.include_router(grading_router)
api_router.include_router(learning_router)
api_router.include_router(tasks_router)
