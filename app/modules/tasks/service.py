import json

from sqlalchemy import select

from app.api.dependencies import DbSession
from app.models.concept import Concept
from app.models.task import Task
from app.schemas.task import TaskCreate


def create_task(db: DbSession, data: TaskCreate) -> Task:
    concept = db.scalar(
        select(Concept).where(Concept.public_id == data.concept_public_id)
    )
    if concept is None:
        raise ValueError("존재하지 않는 concept_public_id입니다.")

    task = Task(
        concept_id=concept.id,
        title=data.title,
        type=data.type,
        domain=data.domain,
        difficulty=data.difficulty,
        description=data.description,
        template_code=data.template_code,
        options=data.options,
        hint_text=data.hint_text,
        test_cases=json.dumps(data.test_cases, ensure_ascii=False),
        correct_option=data.correct_option,
        is_active=True,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task