from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.core.time import game_today
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


def assess_concept(
    db: Session,
    user_id: int,
    concept_id: int,
    since: datetime | None = None,
) -> ConceptAssessment:
    query = (
        select(TaskAttempt.is_correct)
        .join(Task, Task.id == TaskAttempt.task_id)
        .where(
            TaskAttempt.user_id == user_id,
            Task.concept_id == concept_id,
            TaskAttempt.status == "COMPLETED",
        )
    )
    if since is not None:
        query = query.where(TaskAttempt.attempted_at >= since)
    recent = db.execute(
        query.order_by(TaskAttempt.attempted_at.desc(), TaskAttempt.id.desc()).limit(
            RECENT_ATTEMPT_LIMIT
        )
    ).scalars().all()
    level = calculate_proficiency([value is True for value in recent])
    return ConceptAssessment(concept_id, len(recent), level)


def update_proficiency(
    db: Session,
    user_id: int,
    concept_id: int,
    since: datetime | None = None,
) -> UserProficiency:
    assessment = assess_concept(db, user_id, concept_id, since)
    row = db.scalar(select(UserProficiency).where(
        UserProficiency.user_id == user_id, UserProficiency.concept_id == concept_id
    ))
    if row is None:
        row = UserProficiency(user_id=user_id, concept_id=concept_id)
        db.add(row)
    row.proficiency_level = assessment.proficiency_level
    return row


def weak_concepts(
    db: Session,
    user_id: int,
    since: datetime | None = None,
) -> list[ConceptAssessment]:
    return [item for item in concept_assessments(db, user_id, since) if item.is_weak]


def concept_assessments(
    db: Session,
    user_id: int,
    since: datetime | None = None,
) -> list[ConceptAssessment]:
    query = select(Task.concept_id).join(TaskAttempt).where(
        TaskAttempt.user_id == user_id, TaskAttempt.status == "COMPLETED"
    )
    if since is not None:
        query = query.where(TaskAttempt.attempted_at >= since)
    concept_ids = db.scalars(query.distinct().order_by(Task.concept_id)).all()
    return [assess_concept(db, user_id, concept_id, since) for concept_id in concept_ids]


def recommended_tasks(
    db: Session,
    user_id: int,
    limit: int = 10,
    since: datetime | None = None,
    recommendation_date: date | None = None,
) -> list[Task]:
    """Return personalized tasks with a stable order that rotates each game day."""
    weak = sorted(weak_concepts(db, user_id, since), key=lambda item: item.proficiency_level)
    weak_ids = [item.concept_id for item in weak]
    selected_date = recommendation_date or game_today()
    recent_ids = select(TaskAttempt.task_id).where(TaskAttempt.user_id == user_id)
    if since is not None:
        recent_ids = recent_ids.where(TaskAttempt.attempted_at >= since)
    recent_ids = recent_ids.order_by(TaskAttempt.attempted_at.desc(), TaskAttempt.id.desc()).limit(20)
    difficulty_rank = case((Task.difficulty == "BRONZE", 1), (Task.difficulty == "SILVER", 2), else_=3)

    def candidates(exclude_recent: bool, weak_only: bool) -> list[Task]:
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
            query = query.order_by(difficulty_rank, Task.id)
        rows = list(db.scalars(query).all())
        return _rotate_daily_priority_groups(rows, user_id, selected_date, weak_ids)[:limit]

    for exclude_recent, weak_only in ((True, True), (True, False), (False, True), (False, False)):
        if weak_only and not weak_ids:
            continue
        rows = candidates(exclude_recent, weak_only)
        if rows:
            return rows
    return []


def _rotate_daily_priority_groups(
    tasks: list[Task],
    user_id: int,
    recommendation_date: date,
    weak_concept_ids: list[int],
) -> list[Task]:
    """Rotate ties daily without changing concept or difficulty priority."""
    concept_rank = {concept_id: index for index, concept_id in enumerate(weak_concept_ids)}
    difficulty_rank = {"BRONZE": 1, "SILVER": 2, "GOLD": 3}
    groups: dict[tuple[int, int], list[Task]] = {}
    group_order: list[tuple[int, int]] = []
    for task in tasks:
        key = (
            concept_rank.get(task.concept_id, 999),
            difficulty_rank.get(task.difficulty, 3),
        )
        if key not in groups:
            groups[key] = []
            group_order.append(key)
        groups[key].append(task)

    rotated: list[Task] = []
    for key in group_order:
        group = groups[key]
        offset = (recommendation_date.toordinal() + user_id) % len(group)
        rotated.extend(group[offset:] + group[:offset])
    return rotated
