from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.models.user_proficiency import UserProficiency

RECENT_ATTEMPT_LIMIT = 10
MIN_ATTEMPTS_FOR_WEAKNESS = 3
WEAK_PROFICIENCY_MAX = 50


@dataclass(frozen=True)
class ConceptAssessment:
    concept_id: int
    attempts: int
    proficiency_level: int

    @property
    def is_weak(self) -> bool:
        return (
            self.attempts >= MIN_ATTEMPTS_FOR_WEAKNESS
            and self.proficiency_level <= WEAK_PROFICIENCY_MAX
        )


def calculate_proficiency(results: list[bool]) -> int:
    return round(100 * sum(results) / len(results)) if results else 0


def assess_concept(db: Session, user_id: int, concept_id: int) -> ConceptAssessment:
    recent = (
        db.execute(
            select(TaskAttempt.is_correct)
            .join(Task, Task.id == TaskAttempt.task_id)
            .where(
                TaskAttempt.user_id == user_id,
                Task.concept_id == concept_id,
                TaskAttempt.status == "COMPLETED",
            )
            .order_by(TaskAttempt.attempted_at.desc(), TaskAttempt.id.desc())
            .limit(RECENT_ATTEMPT_LIMIT)
        )
        .scalars()
        .all()
    )
    level = calculate_proficiency([value is True for value in recent])
    return ConceptAssessment(concept_id, len(recent), level)


def update_proficiency(db: Session, user_id: int, concept_id: int) -> UserProficiency:
    assessment = assess_concept(db, user_id, concept_id)
    row = db.scalar(
        select(UserProficiency).where(
            UserProficiency.user_id == user_id, UserProficiency.concept_id == concept_id
        )
    )
    if row is None:
        row = UserProficiency(user_id=user_id, concept_id=concept_id)
        db.add(row)
    row.proficiency_level = assessment.proficiency_level
    return row


def weak_concepts(db: Session, user_id: int) -> list[ConceptAssessment]:
    concept_ids = db.scalars(
        select(Task.concept_id)
        .join(TaskAttempt)
        .where(TaskAttempt.user_id == user_id, TaskAttempt.status == "COMPLETED")
        .distinct()
    ).all()
    return [
        item
        for concept_id in concept_ids
        if (item := assess_concept(db, user_id, concept_id)).is_weak
    ]


def recommended_tasks(db: Session, user_id: int, limit: int = 10) -> list[Task]:
    weak = sorted(weak_concepts(db, user_id), key=lambda item: item.proficiency_level)
    weak_ids = [item.concept_id for item in weak]
    recent_ids = (
        select(TaskAttempt.task_id)
        .where(TaskAttempt.user_id == user_id)
        .order_by(TaskAttempt.attempted_at.desc(), TaskAttempt.id.desc())
        .limit(20)
    )
    difficulty_rank = case(
        (Task.difficulty == "BRONZE", 1), (Task.difficulty == "SILVER", 2), else_=3
    )

    def candidates(exclude_recent: bool, weak_only: bool):
        query = select(Task).where(Task.is_active.is_(True))
        if weak_only:
            query = query.where(Task.concept_id.in_(weak_ids))
        if exclude_recent:
            query = query.where(Task.id.not_in(recent_ids))
        if weak_ids:
            concept_rank = case(
                {value: index for index, value in enumerate(weak_ids)},
                value=Task.concept_id,
                else_=999,
            )
            query = query.order_by(concept_rank, difficulty_rank, Task.id)
        else:
            query = query.order_by(difficulty_rank, func.random())
        return db.scalars(query.limit(limit)).all()

    for exclude_recent, weak_only in ((True, True), (True, False), (False, True), (False, False)):
        if weak_only and not weak_ids:
            continue
        rows = candidates(exclude_recent, weak_only)
        if rows:
            return rows
    return []
