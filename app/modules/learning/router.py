from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.models.concept import Concept
from app.models.task_attempt import TaskAttempt
from app.modules.learning.proficiency import recommended_tasks, weak_concepts
from app.schemas.task import TaskRead

router = APIRouter(prefix="/learning", tags=["learning"])


def _task_payload(db: DbSession, task, *, completed: bool):
    concept = db.get(Concept, task.concept_id)
    return {
        "public_id": task.public_id,
        "concept_public_id": concept.public_id,
        "concept_name": concept.name,
        "title": task.title,
        "type": task.type,
        "domain": task.domain,
        "difficulty": task.difficulty,
        "description": task.description,
        "template_code": task.template_code,
        "options": task.options,
        "hint_text": task.hint_text,
        "is_active": task.is_active,
        "completed": completed,
    }


@router.get("/recommendations")
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


@router.get("/weak-concepts")
def weaknesses(db: DbSession, user: CurrentUser):
    rows = []
    for assessment in weak_concepts(db, user.id):
        concept = db.get(Concept, assessment.concept_id)
        rows.append({
            "concept_public_id": concept.public_id,
            "name": concept.name,
            "attempts": assessment.attempts,
            "proficiency_level": assessment.proficiency_level,
        })
    return rows
