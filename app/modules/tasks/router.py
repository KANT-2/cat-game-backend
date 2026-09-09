from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import DbSession, verify_tasks_api_key
from app.modules.tasks.service import create_task
from app.schemas.task import TaskCreate, TaskRead

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskRead, dependencies=[Depends(verify_tasks_api_key)])
def create_task_endpoint(payload: TaskCreate, db: DbSession):
    try:
        task = create_task(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return task