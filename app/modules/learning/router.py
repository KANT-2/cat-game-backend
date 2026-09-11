import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import settings
from app.core.time import game_day_bounds, game_today
from app.models.concept import Concept
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.modules.learning.proficiency import assess_concept, recommended_tasks, weak_concepts
from app.modules.learning.tier import PROMOTION_POLICY, get_or_advance_tier, unlocked_difficulties
from app.schemas.learning_tier import ConceptTierProgressRead, LearningTierRead
from app.schemas.task import TaskRead, to_task_read
from app.schemas.user_proficiency import ConceptProficiencyRead, WeakConceptRead

router = APIRouter(prefix="/learning", tags=["learning"])


def _tier_payload(db: DbSession, user: CurrentUser, domain):
    row, progress = get_or_advance_tier(db, user, domain)
    db.commit()
    return LearningTierRead(
        domain=domain,
        current_tier=row.current_tier,
        unlocked_difficulties=list(unlocked_difficulties(row.current_tier)),
        next_tier=PROMOTION_POLICY.get(row.current_tier, (0, 0, None))[2],
        completed=progress.completed,
        total=progress.total,
        required=progress.required,
        concept_required_percent=progress.concept_required_percent,
        concepts=[
            ConceptTierProgressRead(
                concept_public_id=db.get(Concept, item.concept_id).public_id,
                name=item.name,
                completed=item.completed,
                total=item.total,
                required=item.required,
                is_met=item.is_met,
            )
            for item in progress.concepts
        ],
    )


@router.get("/tier", response_model=LearningTierRead)
def learning_tier(db: DbSession, user: CurrentUser) -> LearningTierRead:
    domain = user.game_settings.get("learningDomain", "PYTHON")
    if domain not in {"PYTHON", "SQL"}:
        domain = "PYTHON"
    return _tier_payload(db, user, domain)


def _recommendation_date(test_date: date | None) -> date:
    if test_date is None:
        return game_today()
    if settings.app_env not in {"local", "test"}:
        raise HTTPException(status_code=404, detail="Not found")
    return test_date


def _task_payload(db: DbSession, task, *, completed: bool) -> TaskRead:
    concept = db.get(Concept, task.concept_id)
    return to_task_read(task, concept, completed=completed)


def _learning_progress_start(learning_reset_at: datetime | None) -> datetime:
    """Return the later of today's boundary and the user's manual reset time."""
    day_start, _ = game_day_bounds(game_today())
    if learning_reset_at is not None and learning_reset_at > day_start:
        return learning_reset_at
    return day_start


def _completed_task_ids(
    db: DbSession,
    user_id: int,
    task_ids: list[int],
    *,
    since=None,
) -> set[int]:
    if not task_ids:
        return set()
    statement = select(TaskAttempt.task_id).where(
        TaskAttempt.user_id == user_id,
        TaskAttempt.task_id.in_(task_ids),
        TaskAttempt.status == "COMPLETED",
        TaskAttempt.is_correct.is_(True),
    )
    if since is not None:
        statement = statement.where(TaskAttempt.attempted_at >= since)
    return set(db.scalars(statement).all())


@router.get("/tasks", response_model=list[TaskRead])
def list_tasks(
    db: DbSession,
    user: CurrentUser,
    task_type: Literal["CODE", "MULTIPLE_CHOICE"] | None = Query(None, alias="type"),
    domain: Literal["PYTHON", "SQL"] | None = Query(None),
    concept_public_id: uuid.UUID | None = None,
    difficulty: Literal["BRONZE", "SILVER", "GOLD"] | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
) -> list[TaskRead]:
    statement = select(Task).join(Concept, Concept.id == Task.concept_id).where(Task.is_active.is_(True))

    tier_domain = domain if isinstance(domain, str) else None
    domains = (tier_domain,) if tier_domain else ("PYTHON", "SQL")
    allowed_by_domain = {}
    for selected_domain in domains:
        tier, _ = get_or_advance_tier(db, user, selected_domain)
        allowed_by_domain[selected_domain] = unlocked_difficulties(tier.current_tier)
    db.commit()
    statement = statement.where(
        or_(
            *(
                (Concept.domain == selected_domain)
                & Task.difficulty.in_(allowed)
                for selected_domain, allowed in allowed_by_domain.items()
            )
        )
    )

    if task_type == "MULTIPLE_CHOICE":
        statement = statement.where(Task.options.is_not(None), Task.difficulty != "GOLD")
    if domain is not None:
        statement = statement.where(Concept.domain == domain)
    if difficulty is not None:
        statement = statement.where(Task.difficulty == difficulty)

    if concept_public_id is not None:
        concept = db.scalar(select(Concept).where(Concept.public_id == concept_public_id))
        if concept is None:
            return []
        statement = statement.where(Task.concept_id == concept.id)

    tasks = list(db.scalars(statement.order_by(Task.id).limit(limit)).all())
    completed_ids = _completed_task_ids(
        db,
        user.id,
        [task.id for task in tasks],
        since=_learning_progress_start(user.learning_reset_at),
    )
    return [_task_payload(db, task, completed=task.id in completed_ids) for task in tasks]


@router.get("/recommendations", response_model=list[TaskRead])
def recommendations(
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(10, ge=1, le=50),
    test_date: Annotated[
        date | None,
        Query(description="Local/test-only recommendation date override."),
    ] = None,
) -> list[TaskRead]:
    preferred_domain = user.game_settings.get("learningDomain", "PYTHON")
    if preferred_domain not in {"PYTHON", "SQL"}:
        preferred_domain = "PYTHON"
    tasks = recommended_tasks(
        db,
        user.id,
        limit,
        since=user.learning_reset_at,
        recommendation_date=_recommendation_date(test_date),
        domain=preferred_domain,
        allowed_difficulties=unlocked_difficulties(
            get_or_advance_tier(db, user, preferred_domain)[0].current_tier
        ),
    )
    db.commit()
    completed_ids = _completed_task_ids(
        db,
        user.id,
        [task.id for task in tasks],
        since=_learning_progress_start(user.learning_reset_at),
    )
    return [_task_payload(db, task, completed=task.id in completed_ids) for task in tasks]


@router.get("/weak-concepts", response_model=list[WeakConceptRead])
def weaknesses(db: DbSession, user: CurrentUser) -> list[WeakConceptRead]:
    rows = []
    for assessment in weak_concepts(db, user.id, since=user.learning_reset_at):
        concept = db.get(Concept, assessment.concept_id)
        rows.append(
            WeakConceptRead(
                concept_public_id=concept.public_id,
                domain=concept.domain,
                name=concept.name,
                attempts=assessment.attempts,
                proficiency_level=assessment.proficiency_level,
            )
        )
    return rows


@router.get("/proficiencies", response_model=list[ConceptProficiencyRead])
def proficiencies(db: DbSession, user: CurrentUser) -> list[ConceptProficiencyRead]:
    preferred_domain = user.game_settings.get("learningDomain", "PYTHON")
    if preferred_domain not in {"PYTHON", "SQL"}:
        preferred_domain = "PYTHON"
    concepts = db.scalars(
        select(Concept).where(Concept.domain == preferred_domain).order_by(Concept.name)
    ).all()
    rows = []
    for concept in concepts:
        assessment = assess_concept(
            db,
            user.id,
            concept.id,
            since=user.learning_reset_at,
        )
        rows.append(
            ConceptProficiencyRead(
                concept_public_id=concept.public_id,
                domain=concept.domain,
                name=concept.name,
                attempts=assessment.attempts,
                proficiency_level=assessment.proficiency_level,
            )
        )
    return rows
