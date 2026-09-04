import uuid
from typing import Literal

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.models.concept import Concept
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.modules.learning.proficiency import recommended_tasks, weak_concepts
from app.schemas.task import TaskRead, to_task_read
from app.schemas.user_proficiency import WeakConceptRead

router = APIRouter(prefix="/learning", tags=["learning"])


def _task_payload(db: DbSession, task, *, completed: bool) -> TaskRead:
    concept = db.get(Concept, task.concept_id)
    return to_task_read(task, concept, completed=completed)


def _completed_task_ids(db: DbSession, user_id: int, task_ids: list[int]) -> set[int]:
    if not task_ids:
        return set()
    return set(
        db.scalars(
            select(TaskAttempt.task_id).where(
                TaskAttempt.user_id == user_id,
                TaskAttempt.task_id.in_(task_ids),
                TaskAttempt.status == "COMPLETED",
                TaskAttempt.is_correct.is_(True),
            )
        ).all()
    )


@router.get("/tasks", response_model=list[TaskRead])
def list_tasks(
    db: DbSession,
    user: CurrentUser,
    task_type: Literal["CODE", "MULTIPLE_CHOICE"] | None = Query(None, alias="type"),
    domain: Literal["PYTHON", "SQL"] | None = Query(None),
    concept_public_id: uuid.UUID | None = None,
    difficulty: Literal["BRONZE", "SILVER", "GOLD"] | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
) -> list[TaskRead]:
    statement = select(Task).where(Task.is_active.is_(True))

    if task_type is not None:
        statement = statement.where(Task.type == task_type)
    if domain is not None:
        statement = statement.where(Task.domain == domain)
    if difficulty is not None:
        statement = statement.where(Task.difficulty == difficulty)

    if concept_public_id is not None:
        concept = db.scalar(select(Concept).where(Concept.public_id == concept_public_id))
        if concept is None:
            return []
        statement = statement.where(Task.concept_id == concept.id)

    tasks = list(db.scalars(statement.order_by(Task.id).limit(limit)).all())
    completed_ids = _completed_task_ids(db, user.id, [task.id for task in tasks])
    return [_task_payload(db, task, completed=task.id in completed_ids) for task in tasks]


@router.get("/recommendations", response_model=list[TaskRead])
def recommendations(
    db: DbSession, user: CurrentUser, limit: int = Query(10, ge=1, le=50)
) -> list[TaskRead]:
    tasks = recommended_tasks(db, user.id, limit)
    completed_ids = _completed_task_ids(db, user.id, [task.id for task in tasks])
    return [_task_payload(db, task, completed=task.id in completed_ids) for task in tasks]


@router.get("/weak-concepts", response_model=list[WeakConceptRead])
def weaknesses(db: DbSession, user: CurrentUser) -> list[WeakConceptRead]:
    rows = []
    for assessment in weak_concepts(db, user.id):
        concept = db.get(Concept, assessment.concept_id)
        rows.append(
            WeakConceptRead(
                concept_public_id=concept.public_id,
                name=concept.name,
                attempts=assessment.attempts,
                proficiency_level=assessment.proficiency_level,
            )
        )
    return rows
