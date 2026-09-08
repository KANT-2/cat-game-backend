import uuid
from random import SystemRandom

from pydantic import BaseModel

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
    reward_coins: int

    # test_cases와 correct_option은 채점 전용 정보라 의도적으로 포함하지 않는다.


class TaskCreate(BaseModel):
    concept_public_id: uuid.UUID
    title: str
    type: str  # "MULTIPLE_CHOICE" 또는 "CODE"
    domain: str
    difficulty: str  # "BRONZE" / "SILVER" / "GOLD"
    description: str
    template_code: str = ""
    options: dict[str, str] | None = None
    hint_text: str | None = None
    test_cases: list[dict] = []
    correct_option: str | None = None


def to_task_read(task: Task, concept: Concept, *, completed: bool = False) -> TaskRead:
    options = task.options
    if options:
        shuffled = list(options.items())
        SystemRandom().shuffle(shuffled)
        options = dict(shuffled)
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
        options=options,
        hint_text=task.hint_text,
        is_active=task.is_active,
        completed=completed,
        reward_coins=task.reward_coins,
    )