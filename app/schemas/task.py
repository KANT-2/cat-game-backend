import uuid
from random import SystemRandom
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.concept import Concept
from app.models.task import Task
from app.schemas.base import ReadSchema


class TaskRead(ReadSchema):
    concept_public_id: uuid.UUID
    concept_name: str
    title: str
    type: str
    domain: Literal["PYTHON", "SQL"]
    difficulty: str
    description: str
    template_code: str
    options: dict[str, str] | None
    hint_text: str | None
    is_active: bool
    completed: bool = False
    reward_coins: int

    # test_cases and correct_option are grading-only fields, intentionally excluded.


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_public_id: uuid.UUID
    title: str
    type: Literal["MULTIPLE_CHOICE", "CODE"]
    domain: Literal["PYTHON", "SQL"]
    difficulty: Literal["BRONZE", "SILVER", "GOLD"]
    description: str
    template_code: str = ""
    options: dict[str, str] | None = None
    hint_text: str | None = None
    test_cases: list[dict] = Field(default_factory=list)
    correct_option: str | None = None


class TaskUpdate(BaseModel):
    """Fields that team members may change on an existing learning task."""

    model_config = ConfigDict(extra="forbid")

    concept_public_id: uuid.UUID | None = None
    title: str | None = None
    type: Literal["MULTIPLE_CHOICE", "CODE"] | None = None
    domain: Literal["PYTHON", "SQL"] | None = None
    difficulty: Literal["BRONZE", "SILVER", "GOLD"] | None = None
    description: str | None = None
    template_code: str | None = None
    options: dict[str, str] | None = None
    hint_text: str | None = None
    test_cases: list[dict] | None = None
    correct_option: str | None = None
    is_active: bool | None = None


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
        domain=concept.domain,
        difficulty=task.difficulty,
        description=task.description,
        template_code=task.template_code,
        options=options,
        hint_text=task.hint_text,
        is_active=task.is_active,
        completed=completed,
        reward_coins=task.reward_coins,
    )
