from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app.db.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyCatMemoryRepository,
    SqlAlchemyCatRepository,
    SqlAlchemyExecutionRepository,
    SqlAlchemyItemRepository,
    SqlAlchemyPlacedObjectRepository,
    SqlAlchemyUserRepository,
)
from app.db.unit_of_work import SqlAlchemyUnitOfWork

EXPECTED_REPOSITORIES = {
    "users": SqlAlchemyUserRepository,
    "items": SqlAlchemyItemRepository,
    "cats": SqlAlchemyCatRepository,
    "assets": SqlAlchemyAssetRepository,
    "executions": SqlAlchemyExecutionRepository,
    "placed_objects": SqlAlchemyPlacedObjectRepository,
    "cat_memories": SqlAlchemyCatMemoryRepository,
}


def test_unit_of_work_opens_one_session_for_all_repositories() -> None:
    session = Mock(spec=Session)
    session_factory = Mock(return_value=session)
    unit_of_work = SqlAlchemyUnitOfWork(session_factory)

    entered = unit_of_work.__enter__()

    assert entered is unit_of_work
    session_factory.assert_called_once_with()

    for name, repository_type in EXPECTED_REPOSITORIES.items():
        repository = getattr(unit_of_work, name)

        assert isinstance(repository, repository_type)
        assert repository._session is session


def test_unit_of_work_commit_delegates_to_session() -> None:
    session = Mock(spec=Session)
    unit_of_work = SqlAlchemyUnitOfWork(Mock(return_value=session))
    unit_of_work.__enter__()

    unit_of_work.commit()

    session.commit.assert_called_once_with()


def test_unit_of_work_rollback_delegates_to_session() -> None:
    session = Mock(spec=Session)
    unit_of_work = SqlAlchemyUnitOfWork(Mock(return_value=session))
    unit_of_work.__enter__()

    unit_of_work.rollback()

    session.rollback.assert_called_once_with()


def test_unit_of_work_exit_rolls_back_and_closes_session() -> None:
    session = Mock(spec=Session)
    unit_of_work = SqlAlchemyUnitOfWork(Mock(return_value=session))
    unit_of_work.__enter__()

    unit_of_work.__exit__(None, None, None)

    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()


def test_unit_of_work_rolls_back_and_closes_when_exception_occurs() -> None:
    session = Mock(spec=Session)
    unit_of_work = SqlAlchemyUnitOfWork(Mock(return_value=session))

    with pytest.raises(RuntimeError, match="service failed"), unit_of_work:
        raise RuntimeError("service failed")

    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()
