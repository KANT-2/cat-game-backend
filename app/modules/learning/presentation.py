from __future__ import annotations

from random import SystemRandom
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.concept import Concept
from app.models.task import Task
from app.models.task_presentation import TaskPresentation
from app.models.user import User
from app.modules.learning.tier import get_or_advance_tier, unlocked_difficulties
from app.schemas.task import TaskRead, to_task_read

MULTIPLE_CHOICE_PROBABILITY = {
    "BRONZE": 0.5,
    "SILVER": 0.2,
    "GOLD": 0.0,
}


class RandomSource(Protocol):
    def random(self) -> float: ...
    def shuffle(self, values: list) -> None: ...


def choose_presentation_type(task: Task, rng: RandomSource) -> str:
    """Choose once from the difficulty policy when a maintained MCQ form exists."""
    probability = MULTIPLE_CHOICE_PROBABILITY[task.difficulty]
    has_multiple_choice = bool(task.options and task.correct_option in task.options)
    return "MULTIPLE_CHOICE" if has_multiple_choice and rng.random() < probability else "CODE"


def shuffled_options(
    options: dict[str, str], correct_option: str, rng: RandomSource
) -> tuple[dict[str, str], str]:
    """Assign shuffled values to stable A/B/C/D labels and return the new answer label."""
    labels = list(options)
    entries = list(options.items())
    rng.shuffle(entries)
    shuffled = {
        label: value for label, (_, value) in zip(labels, entries, strict=True)
    }
    new_correct = next(
        label
        for label, (original_label, _) in zip(labels, entries, strict=True)
        if original_label == correct_option
    )
    return shuffled, new_correct


def start_task_presentation(
    db: Session,
    task_public_id,
    user: User,
    *,
    rng: RandomSource | None = None,
) -> tuple[TaskPresentation, Task, Concept]:
    """Create or reuse the learner's active presentation for one logical task."""
    task = db.scalar(select(Task).where(Task.public_id == task_public_id, Task.is_active.is_(True)))
    if task is None:
        raise LookupError("task not found")
    concept = db.get(Concept, task.concept_id)
    if concept is None:
        raise LookupError("task concept not found")

    tier, _ = get_or_advance_tier(db, user, concept.domain)
    if task.difficulty not in unlocked_difficulties(tier.current_tier):
        raise LookupError("task difficulty is locked")

    db.scalar(select(User).where(User.id == user.id).with_for_update())
    active = db.scalar(
        select(TaskPresentation).where(
            TaskPresentation.user_id == user.id,
            TaskPresentation.task_id == task.id,
            TaskPresentation.context_type == "LEARNING",
            TaskPresentation.status == "ACTIVE",
        )
    )
    if active is not None:
        return active, task, concept

    source = rng or SystemRandom()
    presentation_type = choose_presentation_type(task, source)
    options = correct_option = None
    description = task.description
    if presentation_type == "MULTIPLE_CHOICE":
        options, correct_option = shuffled_options(task.options, task.correct_option, source)
        description = task.multiple_choice_prompt or task.description
    presentation = TaskPresentation(
        user_id=user.id,
        task_id=task.id,
        context_type="LEARNING",
        presentation_type=presentation_type,
        description=description,
        options=options,
        correct_option=correct_option,
        status="ACTIVE",
    )
    db.add(presentation)
    db.commit()
    db.refresh(presentation)
    return presentation, task, concept


def to_presented_task(
    presentation: TaskPresentation,
    task: Task,
    concept: Concept,
    *,
    completed: bool = False,
) -> TaskRead:
    return to_task_read(
        task,
        concept,
        completed=completed,
        presentation_public_id=presentation.public_id,
        presentation_type=presentation.presentation_type,
        presentation_description=presentation.description,
        presentation_options=presentation.options,
    )
