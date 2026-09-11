import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import DbSession, verify_tasks_api_key
from app.modules.tasks.service import create_task, deactivate_task, update_task
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskRead, dependencies=[Depends(verify_tasks_api_key)])
def create_task_endpoint(payload: TaskCreate, db: DbSession):
    try:
        task = create_task(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return task


@router.patch("/{task_public_id}", response_model=TaskRead, dependencies=[Depends(verify_tasks_api_key)])
def update_task_endpoint(task_public_id: uuid.UUID, payload: TaskUpdate, db: DbSession):
    try:
        return update_task(db, task_public_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/{task_public_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_tasks_api_key)],
)
def delete_task_endpoint(task_public_id: uuid.UUID, db: DbSession) -> Response:
    try:
        deactivate_task(db, task_public_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
