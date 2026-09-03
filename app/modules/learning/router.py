from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, DbSession
from app.models.concept import Concept
from app.modules.learning.proficiency import recommended_tasks, weak_concepts
from app.schemas.task import TaskRead

router = APIRouter(prefix="/learning", tags=["learning"])


def _task_payload(db: DbSession, task):
    concept = db.get(Concept, task.concept_id)
    return {
        "public_id": task.public_id,
        "concept_public_id": concept.public_id,
        "title": task.title,
        "type": task.type,
        "domain": task.domain,
        "difficulty": task.difficulty,
        "description": task.description,
        "template_code": task.template_code,
        "options": task.options,
        "hint_text": task.hint_text,
        "is_active": task.is_active,
    }


@router.get("/recommendations")
def recommendations(
    db: DbSession, user: CurrentUser, limit: int = Query(10, ge=1, le=50)
) -> list[TaskRead]:
    return [_task_payload(db, task) for task in recommended_tasks(db, user.id, limit)]


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
