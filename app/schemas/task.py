import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.concept import Concept
from app.models.task import Task
from app.schemas.base import ReadSchema


class TaskRead(ReadSchema):
    presentation_public_id: uuid.UUID | None = None
    presentation_required: bool = False
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
    multiple_choice_prompt: str | None = None
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
    multiple_choice_prompt: str | None = None
    options: dict[str, str] | None = None
    hint_text: str | None = None
    test_cases: list[dict] | None = None
    correct_option: str | None = None
    is_active: bool | None = None


def to_task_read(
    task: Task,
    concept: Concept,
    *,
    completed: bool = False,
    presentation_public_id: uuid.UUID | None = None,
    presentation_type: str | None = None,
    presentation_description: str | None = None,
    presentation_options: dict[str, str] | None = None,
) -> TaskRead:
    resolved_type = presentation_type or task.type
    if presentation_type is None and task.type == "MULTIPLE_CHOICE":
        presentation_description = getattr(task, "multiple_choice_prompt", None) or task.description
        presentation_options = task.options
    return TaskRead(
        public_id=task.public_id,
        concept_public_id=concept.public_id,
        concept_name=getattr(concept, "name", ""),
        title=task.title,
        presentation_public_id=presentation_public_id,
        presentation_required=presentation_public_id is None and bool(task.options),
        type=resolved_type,
        domain=concept.domain,
        difficulty=task.difficulty,
        description=presentation_description or task.description,
        template_code=task.template_code,
        options=presentation_options,
        hint_text=task.hint_text,
        is_active=task.is_active,
        completed=completed,
        reward_coins=task.reward_coins,
    )
