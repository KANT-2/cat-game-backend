import json
import uuid

from sqlalchemy import select

from app.api.dependencies import DbSession
from app.models.concept import Concept
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate, to_task_read


def create_task(db: DbSession, data: TaskCreate) -> TaskRead:
    concept = db.scalar(
        select(Concept).where(Concept.public_id == data.concept_public_id)
    )
    if concept is None:
        raise ValueError("존재하지 않는 concept_public_id입니다.")
    if concept.domain != data.domain:
        raise ValueError("domain은 선택한 concept의 domain과 일치해야 합니다.")

    task = Task(
        concept_id=concept.id,
        title=data.title,
        type=data.type,
        difficulty=data.difficulty,
        description=data.description,
        template_code=data.template_code,
        multiple_choice_prompt=data.multiple_choice_prompt,
        options=data.options,
        hint_text=data.hint_text,
        test_cases=json.dumps(data.test_cases, ensure_ascii=False),
        correct_option=data.correct_option,
        is_active=True,
    )
    if task.type == "MULTIPLE_CHOICE" and task.multiple_choice_prompt is None:
        task.multiple_choice_prompt = task.description
    _validate_grading_metadata(task)
    db.add(task)
    db.commit()
    db.refresh(task)
    return to_task_read(task, concept)


def update_task(db: DbSession, task_public_id: uuid.UUID, data: TaskUpdate) -> TaskRead:
    """Update an authored task and return its public representation."""
    task = db.scalar(select(Task).where(Task.public_id == task_public_id))
    if task is None:
        raise LookupError("존재하지 않는 문제입니다.")

    concept = db.get(Concept, task.concept_id)
    if data.concept_public_id is not None:
        concept = db.scalar(select(Concept).where(Concept.public_id == data.concept_public_id))
        if concept is None:
            raise ValueError("존재하지 않는 concept_public_id입니다.")

    if data.domain is not None and data.domain != concept.domain:
        raise ValueError("domain은 선택한 concept의 domain과 일치해야 합니다.")

    changes = data.model_dump(exclude_unset=True, exclude={"concept_public_id", "domain"})
    for field in ("title", "type", "difficulty", "description", "template_code", "is_active"):
        if field in changes and changes[field] is None:
            raise ValueError(f"{field}은 null일 수 없습니다.")
    if "test_cases" in changes:
        if changes["test_cases"] is None:
            raise ValueError("test_cases는 null일 수 없습니다.")
        changes["test_cases"] = json.dumps(changes["test_cases"], ensure_ascii=False)

    task.concept_id = concept.id
    for field, value in changes.items():
        setattr(task, field, value)
    if task.type == "MULTIPLE_CHOICE" and task.multiple_choice_prompt is None:
        task.multiple_choice_prompt = task.description
    _validate_grading_metadata(task)
    db.commit()
    db.refresh(task)
    return to_task_read(task, concept)


def deactivate_task(db: DbSession, task_public_id: uuid.UUID) -> None:
    """Hide a task from learners while retaining attempts that reference it."""
    task = db.scalar(select(Task).where(Task.public_id == task_public_id))
    if task is None:
        raise LookupError("존재하지 않는 문제입니다.")
    task.is_active = False
    db.commit()


def _validate_grading_metadata(task: Task) -> None:
    fields = (getattr(task, "multiple_choice_prompt", None), task.options, task.correct_option)
    if any(value is not None for value in fields) and not all(value is not None for value in fields):
        raise ValueError("객관식 prompt, options와 correct_option은 함께 설정해야 합니다.")
    if task.type == "MULTIPLE_CHOICE" and not all(value is not None for value in fields):
        raise ValueError("MULTIPLE_CHOICE 문제에는 객관식 데이터가 필요합니다.")
