from collections.abc import Callable
from types import TracebackType
from typing import Self

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
from app.db.session import SessionLocal


class SqlAlchemyUnitOfWork:
    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
    ) -> None:
        self._session_factory = session_factory

    def __enter__(self) -> Self:
        self._session = self._session_factory()

        self.users = SqlAlchemyUserRepository(self._session)
        self.items = SqlAlchemyItemRepository(self._session)
        self.cats = SqlAlchemyCatRepository(self._session)
        self.assets = SqlAlchemyAssetRepository(self._session)
        self.executions = SqlAlchemyExecutionRepository(self._session)
        self.placed_objects = SqlAlchemyPlacedObjectRepository(self._session)
        self.cat_memories = SqlAlchemyCatMemoryRepository(self._session)

        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        try:
            self.rollback()
        finally:
            self._session.close()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
