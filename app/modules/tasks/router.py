from fastapi import APIRouter, HTTPException

from app.api.dependencies import CurrentUser, DbSession
from app.modules.tasks.service import create_task
from app.schemas.task import TaskCreate, TaskRead

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskRead)
def create_task_endpoint(payload: TaskCreate, db: DbSession, user: CurrentUser):
    try:
        task = create_task(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return task