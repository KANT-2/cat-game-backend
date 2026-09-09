import uuid

from sqlalchemy import func, select

from app.core.repository_contracts import CatalogItemSeed
from app.db.repositories import SqlAlchemyItemRepository
from app.models.item import Item


def test_item_catalog_ensure_is_idempotent_in_postgresql(db_session):
    catalog_key = f"test.gacha-catalog.{uuid.uuid4()}"
    seed = CatalogItemSeed(
        public_id=uuid.uuid4(),
        catalog_key=catalog_key,
        category="FURNITURE",
        name="가챠 카탈로그 테스트",
        price=100,
    )
    repository = SqlAlchemyItemRepository(db_session)

    repository.ensure_catalog_items([seed])
    repository.ensure_catalog_items([seed])
    db_session.flush()

    count = db_session.scalar(
        select(func.count()).select_from(Item).where(Item.catalog_key == catalog_key)
    )
    assert count == 1
