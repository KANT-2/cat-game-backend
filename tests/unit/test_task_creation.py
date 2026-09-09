import uuid
from types import SimpleNamespace

import pytest

from app.modules.tasks.service import create_task
from app.schemas.task import TaskCreate


class _TaskCreationSession:
    def __init__(self, concept):
        self.concept = concept
        self.added = None

    def scalar(self, _statement):
        return self.concept

    def add(self, task):
        self.added = task

    def commit(self):
        pass

    def refresh(self, task):
        task.public_id = uuid.uuid4()
        task.reward_coins = 0


def _payload(concept_public_id: uuid.UUID, domain: str = "SQL") -> TaskCreate:
    return TaskCreate(
        concept_public_id=concept_public_id,
        title="SELECT 기초",
        type="CODE",
        domain=domain,
        difficulty="BRONZE",
        description="값을 조회하세요.",
        test_cases=[],
    )


def test_task_creation_uses_concept_as_the_domain_source() -> None:
    concept = SimpleNamespace(
        id=7,
        public_id=uuid.uuid4(),
        domain="SQL",
        name="basics",
    )
    db = _TaskCreationSession(concept)

    result = create_task(db, _payload(concept.public_id))

    assert result.domain == "SQL"
    assert result.concept_name == "basics"
    assert "domain" not in db.added.__dict__


def test_task_creation_rejects_a_domain_that_disagrees_with_the_concept() -> None:
    concept = SimpleNamespace(
        id=7,
        public_id=uuid.uuid4(),
        domain="PYTHON",
        name="basics",
    )
    db = _TaskCreationSession(concept)

    with pytest.raises(ValueError, match="concept의 domain과 일치"):
        create_task(db, _payload(concept.public_id, domain="SQL"))

    assert db.added is None
