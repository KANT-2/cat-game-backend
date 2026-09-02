from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.repository_contracts import (
    ClaimStatus,
    ExecutionClaim,
)
from app.models.cat import Cat
from app.models.cat_memory import CatMemory
from app.models.gacha_execution import GachaExecution
from app.models.item import Item
from app.models.placed_object import PlacedObject
from app.models.user import User
from app.models.user_cat import UserCat


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_public_id(self, public_id: UUID) -> User | None:
        statement = select(User).where(User.public_id == public_id)
        return self._session.execute(statement).scalar_one_or_none()

    def get_for_update(self, user_id: int) -> User | None:
        statement = (
            select(User)
            .where(User.id == user_id)
            .with_for_update()
        )
        return self._session.execute(statement).scalar_one_or_none()

class SqlAlchemyItemRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_public_id(self, public_id: UUID) -> Item | None:
        statement = select(Item).where(Item.public_id == public_id)
        return self._session.execute(statement).scalar_one_or_none()


class SqlAlchemyCatRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_public_id(self, public_id: UUID) -> Cat | None:
        statement = select(Cat).where(Cat.public_id == public_id)
        return self._session.execute(statement).scalar_one_or_none()

class SqlAlchemyAssetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_cat_asset(
        self,
        user_id: int,
        cat_id: int,
    ) -> UserCat | None:
        statement = select(UserCat).where(
            UserCat.user_id == user_id,
            UserCat.cat_id == cat_id,
        )
        return self._session.execute(statement).scalar_one_or_none()

    def get_item_asset_for_update(
        self,
        user_id: int,
        item_id: int,
    ) -> UserCat | None:
        statement = (
            select(UserCat)
            .where(
                UserCat.user_id == user_id,
                UserCat.item_id == item_id,
            )
            .with_for_update()
        )
        return self._session.execute(statement).scalar_one_or_none()

    def add_item_quantity(
        self,
        user_id: int,
        item_id: int,
        quantity: int,
    ) -> UserCat:
        if quantity <= 0:
            raise ValueError("quantity must be positive")

        existing = self.get_item_asset_for_update(user_id, item_id)
        if existing is not None:
            existing.quantity += quantity
            return existing

        asset = UserCat(
            user_id=user_id,
            cat_id=None,
            item_id=item_id,
            quantity=quantity,
        )
        self._session.add(asset)
        return asset

    def grant_cat(
        self,
        user_id: int,
        cat_id: int,
    ) -> UserCat:
        existing = self.get_cat_asset(user_id, cat_id)
        if existing is not None:
            return existing

        asset = UserCat(
            user_id=user_id,
            cat_id=cat_id,
            item_id=None,
            quantity=1,
        )
        self._session.add(asset)
        return asset

class SqlAlchemyPlacedObjectRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def count_for_update(
        self,
        user_id: int,
        item_id: int,
    ) -> int:
        statement = (
            select(PlacedObject)
            .where(
                PlacedObject.user_id == user_id,
                PlacedObject.item_id == item_id,
            )
            .with_for_update()
        )
        placed_objects = self._session.execute(statement).scalars().all()
        return len(placed_objects)

    def add(
        self,
        user_id: int,
        item_id: int,
        position_data: dict[str, object],
    ) -> PlacedObject:
        placed_object = PlacedObject(
            user_id=user_id,
            item_id=item_id,
            position_data=dict(position_data),
        )
        self._session.add(placed_object)
        return placed_object

class SqlAlchemyCatMemoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_user_cat_id(
        self,
        user_cat_id: int,
    ) -> list[CatMemory]:
        statement = (
            select(CatMemory)
            .where(CatMemory.user_cat_id == user_cat_id)
            .order_by(CatMemory.created_at, CatMemory.id)
        )
        return list(self._session.execute(statement).scalars().all())

    def add(
        self,
        user_cat_id: int,
        context_summary: str,
    ) -> CatMemory:
        memory = CatMemory(
            user_cat_id=user_cat_id,
            context_summary=context_summary,
        )
        self._session.add(memory)
        return memory

class SqlAlchemyExecutionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def claim(
        self,
        *,
        user_id: int,
        request_id: UUID,
        request_hash: str,
        request_payload: dict[str, object],
        operation_type: str,
    ) -> ExecutionClaim:
        insert_statement = (
            insert(GachaExecution)
            .values(
                user_id=user_id,
                request_id=request_id,
                request_hash=request_hash,
                request_payload=dict(request_payload),
                operation_type=operation_type,
                status=ClaimStatus.ACQUIRED,
                balance_cost=0,
            )
            .on_conflict_do_nothing(
                index_elements=[GachaExecution.request_id]
            )
            .returning(GachaExecution)
        )

        execution = self._session.execute(
            insert_statement
        ).scalar_one_or_none()

        if execution is not None:
            return ExecutionClaim(
                status=ClaimStatus.ACQUIRED,
                execution=execution,
            )

        select_statement = (
            select(GachaExecution)
            .where(GachaExecution.request_id == request_id)
            .with_for_update()
        )
        execution = self._session.execute(
            select_statement
        ).scalar_one()

        if (
            execution.user_id != user_id
            or execution.request_hash != request_hash
        ):
            return ExecutionClaim(
                status=ClaimStatus.HASH_CONFLICT,
                execution=execution,
            )

        status = (
            ClaimStatus.COMPLETED
            if execution.status == ClaimStatus.COMPLETED
            else ClaimStatus.ACQUIRED
        )
        return ExecutionClaim(status=status, execution=execution)

    def complete(
        self,
        execution: GachaExecution,
        *,
        balance_cost: int,
        result_data: dict[str, object],
    ) -> None:
        if balance_cost < 0:
            raise ValueError("balance_cost must be nonnegative")

        execution.balance_cost = balance_cost
        execution.result_data = dict(result_data)
        execution.status = ClaimStatus.COMPLETED
        execution.completed_at = datetime.now(UTC)