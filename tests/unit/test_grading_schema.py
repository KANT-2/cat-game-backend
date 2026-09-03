import uuid

import pytest
from pydantic import ValidationError

from app.schemas.task_attempt import TaskAttemptCreate


def valid(**changes):
    data = {
        "task_public_id": uuid.uuid4(),
        "submitted_code": "print(input())",
        "context_type": "LEARNING",
    }
    data.update(changes)
    return data


def test_submission_rejects_user_id_and_blank_code():
    with pytest.raises(ValidationError):
        TaskAttemptCreate.model_validate(valid(user_id=1))
    with pytest.raises(ValidationError):
        TaskAttemptCreate.model_validate(valid(submitted_code="  \n"))


@pytest.mark.parametrize("context", ["RANKING", "ranking", "OTHER"])
def test_submission_allows_only_current_contexts(context):
    with pytest.raises(ValidationError):
        TaskAttemptCreate.model_validate(valid(context_type=context))


def test_context_link_combinations_are_enforced():
    TaskAttemptCreate.model_validate(valid())
    TaskAttemptCreate.model_validate(valid(
        context_type="DAILY", attendance_task_public_id=uuid.uuid4()
    ))
    TaskAttemptCreate.model_validate(valid(
        context_type="BATTLE", room_task_public_id=uuid.uuid4()
    ))
    with pytest.raises(ValidationError):
        TaskAttemptCreate.model_validate(valid(context_type="DAILY"))
