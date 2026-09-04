import json
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.schemas.base import ReadSchema


class TaskAttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_public_id: uuid.UUID
    submitted_code: str | None = None
    selected_option: str | None = None
    context_type: Literal["LEARNING", "DAILY", "BATTLE"]
    used_hint: bool = False
    attendance_task_public_id: uuid.UUID | None = None
    room_task_public_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_context_links(self):
        has_code = bool(self.submitted_code and self.submitted_code.strip())
        has_option = bool(self.selected_option and self.selected_option.strip())
        if has_code == has_option:
            raise ValueError("submit exactly one of submitted_code or selected_option")
        links = (self.attendance_task_public_id, self.room_task_public_id)
        expected = {
            "LEARNING": (False, False),
            "DAILY": (True, False),
            "BATTLE": (False, True),
        }[self.context_type]
        if tuple(value is not None for value in links) != expected:
            raise ValueError("context public_id combination is invalid")
        return self


class TaskAttemptAccepted(BaseModel):
    public_id: uuid.UUID
    status: Literal["PENDING"]


class GradingResultDetail(BaseModel):
    verdict: Literal[
        "ACCEPTED",
        "WRONG_ANSWER",
        "SYNTAX_ERROR",
        "RUNTIME_ERROR",
        "TIMEOUT",
        "OUTPUT_LIMIT",
        "SYSTEM_ERROR",
    ]
    detail: str | None = None
    passed: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)


def _parse_result_detail(raw: str | None) -> GradingResultDetail | None:
    if raw is None:
        return None
    try:
        return GradingResultDetail.model_validate(json.loads(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


class TaskAttemptRead(ReadSchema):
    task_public_id: uuid.UUID
    context_type: str
    status: str
    is_correct: bool | None
    used_hint: bool
    attempted_at: datetime
    result_detail: GradingResultDetail | None = None


def to_task_attempt_read(attempt: TaskAttempt, task: Task) -> TaskAttemptRead:
    return TaskAttemptRead(
        public_id=attempt.public_id,
        task_public_id=task.public_id,
        context_type=attempt.context_type,
        status=attempt.status,
        is_correct=attempt.is_correct,
        used_hint=attempt.used_hint,
        attempted_at=attempt.attempted_at,
        result_detail=_parse_result_detail(attempt.result_detail),
    )
