import uuid

from app.models.concept import Concept
from app.models.task import Task
from app.schemas.base import ReadSchema


class TaskRead(ReadSchema):
    concept_public_id: uuid.UUID
    concept_name: str
    title: str
    type: str
    domain: str
    difficulty: str
    description: str
    template_code: str
    options: dict[str, str] | None
    hint_text: str | None
    is_active: bool
    completed: bool = False

    # test_cases와 correct_option은 채점 전용 정보라 의도적으로 포함하지 않는다.


def to_task_read(task: Task, concept: Concept, *, completed: bool = False) -> TaskRead:
    return TaskRead(
        public_id=task.public_id,
        concept_public_id=concept.public_id,
        concept_name=getattr(concept, "name", ""),
        title=task.title,
        type=task.type,
        domain=task.domain,
        difficulty=task.difficulty,
        description=task.description,
        template_code=task.template_code,
        options=task.options,
        hint_text=task.hint_text,
        is_active=task.is_active,
        completed=completed,
    )
