import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.core.time import game_today
from app.models.concept import Concept
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
    domain: Literal["PYTHON", "SQL"] | None = None,
    allowed_difficulties: tuple[str, ...] | None = None,
) -> list[Task]:
    """Return recent-safe, concept-diverse tasks in a user-specific daily order."""
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
        if domain is not None:
            query = query.join(Concept, Concept.id == Task.concept_id).where(Concept.domain == domain)
        if allowed_difficulties is not None:
            query = query.where(Task.difficulty.in_(allowed_difficulties))
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
        return _diversify_daily_tasks(rows, user_id, selected_date, weak_ids, limit)

    for exclude_recent, weak_only in ((True, True), (True, False), (False, True), (False, False)):
        if weak_only and not weak_ids:
            continue
        rows = candidates(exclude_recent, weak_only)
        if rows:
            return rows
    return []


def _diversify_daily_tasks(
    tasks: list[Task],
    user_id: int,
    recommendation_date: date,
    weak_concept_ids: list[int],
    limit: int,
) -> list[Task]:
    """Round-robin concepts while keeping weak and easier tasks ahead of harder ones."""
    concept_rank = {concept_id: index for index, concept_id in enumerate(weak_concept_ids)}
    difficulty_rank = {"BRONZE": 1, "SILVER": 2, "GOLD": 3}
    by_concept: dict[int, list[Task]] = {}
    for task in tasks:
        by_concept.setdefault(task.concept_id, []).append(task)

    concept_order = sorted(
        by_concept,
        key=lambda concept_id: (
            concept_rank.get(concept_id, 999),
            _daily_random_rank(user_id, recommendation_date, f"concept:{concept_id}"),
        ),
    )
    task_positions = _rotated_task_positions(
        by_concept,
        user_id,
        recommendation_date,
        difficulty_rank,
    )
    selected: list[Task] = []
    selected_problem_keys: set[str] = set()
    while len(selected) < limit:
        added = False
        for concept_id in concept_order:
            candidates = by_concept[concept_id]
            while candidates:
                task = min(
                    candidates,
                    key=lambda item: (
                        difficulty_rank.get(item.difficulty, 3),
                        task_positions[item.id],
                    ),
                )
                candidates.remove(task)
                problem_key = _task_problem_key(task)
                if problem_key in selected_problem_keys:
                    continue
                selected.append(task)
                selected_problem_keys.add(problem_key)
                added = True
                break
            if len(selected) == limit:
                return selected
        if not added:
            break
    return selected


def _task_problem_key(task: Task) -> str:
    """Identify one learner-visible problem across seeded story variants."""
    title = getattr(task, "title", "")
    description = getattr(task, "description", "")
    if title.startswith("[SAMPLE:"):
        match = re.search(r"\[문제\]\s*(.*?)(?:\r?\n\s*\r?\n|\Z)", description, re.DOTALL)
        if match:
            prompt = " ".join(match.group(1).split()).casefold()
            return f"seed:{task.concept_id}:{task.difficulty}:{prompt}"
    return f"task:{task.id}"


def _daily_random_rank(user_id: int, recommendation_date: date, value: str) -> bytes:
    seed = f"{user_id}:{recommendation_date.isoformat()}:{value}".encode()
    return hashlib.blake2b(seed, digest_size=8).digest()


def _rotated_task_positions(
    by_concept: dict[int, list[Task]],
    user_id: int,
    recommendation_date: date,
    difficulty_rank: dict[str, int],
) -> dict[int, int]:
    positions: dict[int, int] = {}
    for concept_id, tasks in by_concept.items():
        by_difficulty: dict[int, list[Task]] = {}
        for task in tasks:
            rank = difficulty_rank.get(task.difficulty, 3)
            by_difficulty.setdefault(rank, []).append(task)
        position = 0
        for rank in sorted(by_difficulty):
            group = sorted(
                by_difficulty[rank],
                key=lambda task: _user_random_rank(user_id, f"task:{task.id}"),
            )
            offset = (recommendation_date.toordinal() + user_id + concept_id) % len(group)
            for task in group[offset:] + group[:offset]:
                positions[task.id] = position
                position += 1
    return positions


def _user_random_rank(user_id: int, value: str) -> bytes:
    return hashlib.blake2b(f"{user_id}:{value}".encode(), digest_size=8).digest()
