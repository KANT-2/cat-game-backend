"""Create or update the stable game catalog without duplicating rows."""

from __future__ import annotations

import argparse
import uuid

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.cat import Cat
from app.models.item import Item
from app.modules.game.catalog import CAT_DEFINITIONS, ITEM_DEFINITIONS

CATALOG_NAMESPACE = uuid.UUID("cf4c878d-b1d4-4f10-9c30-d79842280272")


def catalog_public_id(kind: str, catalog_key: str) -> uuid.UUID:
    """Return the deterministic public UUID for one stable catalog entry."""
    return uuid.uuid5(CATALOG_NAMESPACE, f"{kind}:{catalog_key}")


def seed_catalog(*, dry_run: bool = False) -> dict[str, int | bool]:
    """Upsert the complete game catalog in one transaction.

    @param dry_run: Roll back the transaction after calculating changes when true.
    @returns Counts of newly created and updated rows and the selected dry-run mode.
    """
    db = SessionLocal()
    try:
        cats = {row.catalog_key: row for row in db.scalars(select(Cat)).all()}
        items = {row.catalog_key: row for row in db.scalars(select(Item)).all()}
        created = 0
        updated = 0

        for definition in CAT_DEFINITIONS:
            values = {
                "name": definition.name,
                "persona": definition.persona,
                "rarity": definition.rarity,
            }
            row = cats.get(definition.catalog_key)
            if row is None:
                db.add(
                    Cat(
                        public_id=catalog_public_id("cat", definition.catalog_key),
                        catalog_key=definition.catalog_key,
                        **values,
                    )
                )
                created += 1
            else:
                for key, value in values.items():
                    setattr(row, key, value)
                updated += 1

        for definition in ITEM_DEFINITIONS:
            values = {
                "category": definition.category,
                "name": definition.name,
                "price": definition.price,
            }
            row = items.get(definition.catalog_key)
            if row is None:
                db.add(
                    Item(
                        public_id=catalog_public_id("item", definition.catalog_key),
                        catalog_key=definition.catalog_key,
                        **values,
                    )
                )
                created += 1
            else:
                for key, value in values.items():
                    setattr(row, key, value)
                updated += 1

        if dry_run:
            db.rollback()
        else:
            db.commit()
        return {"created": created, "updated": updated, "dry_run": dry_run}
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(seed_catalog(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
