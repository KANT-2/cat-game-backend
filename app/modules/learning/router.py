from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.models.concept import Concept
from app.models.task_attempt import TaskAttempt
from app.modules.learning.proficiency import recommended_tasks, weak_concepts
from app.schemas.task import TaskRead, to_task_read
from app.schemas.user_proficiency import WeakConceptRead

router = APIRouter(prefix="/learning", tags=["learning"])


def _task_payload(db: DbSession, task, *, completed: bool) -> TaskRead:
    concept = db.get(Concept, task.concept_id)
    return to_task_read(task, concept, completed=completed)


@router.get("/recommendations", response_model=list[TaskRead])
def recommendations(
    db: DbSession, user: CurrentUser, limit: int = Query(10, ge=1, le=50)
) -> list[TaskRead]:
    tasks = recommended_tasks(db, user.id, limit)
    task_ids = [task.id for task in tasks]
    completed_ids = set(db.scalars(
        select(TaskAttempt.task_id).where(
            TaskAttempt.user_id == user.id,
            TaskAttempt.task_id.in_(task_ids),
            TaskAttempt.status == "COMPLETED",
            TaskAttempt.is_correct.is_(True),
        )
    ).all()) if task_ids else set()
    return [_task_payload(db, task, completed=task.id in completed_ids) for task in tasks]


@router.get("/weak-concepts", response_model=list[WeakConceptRead])
def weaknesses(db: DbSession, user: CurrentUser) -> list[WeakConceptRead]:
    rows = []
    for assessment in weak_concepts(db, user.id):
        concept = db.get(Concept, assessment.concept_id)
        rows.append(WeakConceptRead(
            concept_public_id=concept.public_id,
            name=concept.name,
            attempts=assessment.attempts,
            proficiency_level=assessment.proficiency_level,
        ))
    return rows
