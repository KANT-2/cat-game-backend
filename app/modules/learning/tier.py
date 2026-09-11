from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from typing import Literal

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models.concept import Concept
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.models.user import User
from app.models.user_learning_tier import UserLearningTier

Tier = Literal["BRONZE", "SILVER", "GOLD"]
Domain = Literal["PYTHON", "SQL"]
TIER_ORDER: tuple[Tier, ...] = ("BRONZE", "SILVER", "GOLD")
PROMOTION_POLICY = {
    "BRONZE": (40, 50, "SILVER"),
    "SILVER": (45, 60, "GOLD"),
}


@dataclass(frozen=True)
class ConceptTierProgress:
    concept_id: int
    name: str
    completed: int
    total: int
    required: int

    @property
    def is_met(self) -> bool:
        return self.completed >= self.required


@dataclass(frozen=True)
class TierProgress:
    difficulty: Tier
    completed: int
    total: int
    required: int
    concept_required_percent: int
    concepts: tuple[ConceptTierProgress, ...]

    @property
    def is_met(self) -> bool:
        return self.completed >= self.required and all(item.is_met for item in self.concepts)


def unlocked_difficulties(tier: Tier) -> tuple[Tier, ...]:
    return TIER_ORDER[: TIER_ORDER.index(tier) + 1]


def tier_progress(db: Session, user: User, domain: Domain, difficulty: Tier) -> TierProgress:
    policy = PROMOTION_POLICY.get(difficulty)
    required, concept_percent = (policy[0], policy[1]) if policy else (0, 0)
    totals = db.execute(
        select(Concept.id, Concept.name, func.count(Task.id))
        .join(Task, Task.concept_id == Concept.id)
        .where(Concept.domain == domain, Task.difficulty == difficulty, Task.is_active.is_(True))
        .group_by(Concept.id, Concept.name)
        .order_by(Concept.name)
    ).all()
    completed_query = (
        select(Task.concept_id, func.count(distinct(TaskAttempt.task_id)))
        .join(TaskAttempt, TaskAttempt.task_id == Task.id)
        .join(Concept, Concept.id == Task.concept_id)
        .where(
            TaskAttempt.user_id == user.id,
            TaskAttempt.status == "COMPLETED",
            TaskAttempt.is_correct.is_(True),
            Concept.domain == domain,
            Task.difficulty == difficulty,
            Task.is_active.is_(True),
        )
        .group_by(Task.concept_id)
    )
    if user.learning_reset_at is not None:
        completed_query = completed_query.where(TaskAttempt.attempted_at >= user.learning_reset_at)
    completed_by_concept = dict(db.execute(completed_query).all())
    concepts = tuple(
        ConceptTierProgress(
            concept_id=concept_id,
            name=name,
            completed=completed_by_concept.get(concept_id, 0),
            total=total,
            required=ceil(total * concept_percent / 100),
        )
        for concept_id, name, total in totals
    )
    return TierProgress(
        difficulty=difficulty,
        completed=sum(item.completed for item in concepts),
        total=sum(item.total for item in concepts),
        required=required,
        concept_required_percent=concept_percent,
        concepts=concepts,
    )


def get_or_advance_tier(db: Session, user: User, domain: Domain) -> tuple[UserLearningTier, TierProgress]:
    # Serialize first-time row creation and promotion checks per user. This also
    # prevents two simultaneous correct submissions from racing the unique row.
    db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    row = db.scalar(
        select(UserLearningTier)
        .where(UserLearningTier.user_id == user.id, UserLearningTier.domain == domain)
        .with_for_update()
    )
    if row is None:
        row = UserLearningTier(user_id=user.id, domain=domain, current_tier="BRONZE")
        db.add(row)
        db.flush()
    while row.current_tier in PROMOTION_POLICY:
        progress = tier_progress(db, user, domain, row.current_tier)
        if not progress.is_met:
            return row, progress
        now = datetime.now(UTC)
        next_tier = PROMOTION_POLICY[row.current_tier][2]
        if next_tier == "SILVER":
            row.silver_unlocked_at = now
        else:
            row.gold_unlocked_at = now
        row.current_tier = next_tier
        row.updated_at = now
    return row, tier_progress(db, user, domain, row.current_tier)
