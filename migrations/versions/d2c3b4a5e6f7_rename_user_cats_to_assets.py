"""rename user cats to assets

Revision ID: d2c3b4a5e6f7
Revises: be8999b8f41e
Create Date: 2026-09-03 14:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d2c3b4a5e6f7"
down_revision: str | Sequence[str] | None = "be8999b8f41e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_asset_references(
    *,
    asset_table: str,
    memory_asset_column: str,
    reverse_function: str,
) -> None:
    op.execute(f"""
        CREATE OR REPLACE FUNCTION trg_fn_users_validate_surface_asset()
        RETURNS TRIGGER AS $$
        DECLARE
            v_category VARCHAR;
        BEGIN
            IF NEW.wallpaper_item_id IS NOT NULL THEN
                SELECT category INTO v_category FROM items WHERE id = NEW.wallpaper_item_id;
                IF v_category IS NULL THEN
                    RAISE EXCEPTION 'wallpaper_item_id % does not reference an existing item', NEW.wallpaper_item_id;
                END IF;
                IF v_category <> 'WALLPAPER' THEN
                    RAISE EXCEPTION 'wallpaper_item_id % is not a WALLPAPER item (category=%)', NEW.wallpaper_item_id, v_category;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM {asset_table}
                    WHERE user_id = NEW.id AND item_id = NEW.wallpaper_item_id
                ) THEN
                    RAISE EXCEPTION 'user % does not own item % and cannot set it as wallpaper', NEW.id, NEW.wallpaper_item_id;
                END IF;
            END IF;

            IF NEW.floor_item_id IS NOT NULL THEN
                SELECT category INTO v_category FROM items WHERE id = NEW.floor_item_id;
                IF v_category IS NULL THEN
                    RAISE EXCEPTION 'floor_item_id % does not reference an existing item', NEW.floor_item_id;
                END IF;
                IF v_category <> 'FLOOR' THEN
                    RAISE EXCEPTION 'floor_item_id % is not a FLOOR item (category=%)', NEW.floor_item_id, v_category;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM {asset_table}
                    WHERE user_id = NEW.id AND item_id = NEW.floor_item_id
                ) THEN
                    RAISE EXCEPTION 'user % does not own item % and cannot set it as floor', NEW.id, NEW.floor_item_id;
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute(f"""
        CREATE OR REPLACE FUNCTION trg_fn_placed_objects_validate_inventory()
        RETURNS TRIGGER AS $$
        DECLARE
            v_category VARCHAR;
            v_owned_quantity INTEGER;
            v_placed_count INTEGER;
        BEGIN
            SELECT category INTO v_category FROM items WHERE id = NEW.item_id;
            IF v_category IS NULL THEN
                RAISE EXCEPTION 'item_id % does not reference an existing item', NEW.item_id;
            END IF;
            IF v_category <> 'FURNITURE' THEN
                RAISE EXCEPTION 'item_id % is not a FURNITURE item (category=%)', NEW.item_id, v_category;
            END IF;

            SELECT quantity INTO v_owned_quantity
            FROM {asset_table}
            WHERE user_id = NEW.user_id AND item_id = NEW.item_id
            FOR UPDATE;

            IF v_owned_quantity IS NULL THEN
                RAISE EXCEPTION 'user % does not own item % and cannot place it', NEW.user_id, NEW.item_id;
            END IF;

            SELECT count(*) INTO v_placed_count
            FROM placed_objects
            WHERE user_id = NEW.user_id AND item_id = NEW.item_id
              AND id <> COALESCE(NEW.id, -1);

            IF v_placed_count + 1 > v_owned_quantity THEN
                RAISE EXCEPTION 'user % cannot place another instance of item % (owned=%, already placed=%)', NEW.user_id, NEW.item_id, v_owned_quantity, v_placed_count;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute(f"""
        CREATE OR REPLACE FUNCTION {reverse_function}()
        RETURNS TRIGGER AS $$
        DECLARE
            v_new_quantity INTEGER;
            v_placed_count INTEGER;
            v_selected_as_surface BOOLEAN;
            v_memory_count INTEGER;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                v_new_quantity := 0;
            ELSE
                v_new_quantity := NEW.quantity;
            END IF;

            IF OLD.item_id IS NOT NULL THEN
                PERFORM 1 FROM placed_objects
                WHERE user_id = OLD.user_id AND item_id = OLD.item_id
                FOR UPDATE;

                SELECT count(*) INTO v_placed_count
                FROM placed_objects
                WHERE user_id = OLD.user_id AND item_id = OLD.item_id;

                IF v_placed_count > v_new_quantity THEN
                    RAISE EXCEPTION 'cannot reduce item % quantity below % currently placed instances', OLD.item_id, v_placed_count;
                END IF;

                SELECT EXISTS (
                    SELECT 1 FROM users
                    WHERE id = OLD.user_id
                      AND (wallpaper_item_id = OLD.item_id OR floor_item_id = OLD.item_id)
                ) INTO v_selected_as_surface;

                IF v_selected_as_surface AND v_new_quantity = 0 THEN
                    RAISE EXCEPTION 'cannot remove item % while it is selected as wallpaper or floor', OLD.item_id;
                END IF;
            END IF;

            IF OLD.cat_id IS NOT NULL AND v_new_quantity = 0 THEN
                SELECT count(*) INTO v_memory_count
                FROM cat_memories
                WHERE {memory_asset_column} = OLD.id;

                IF v_memory_count > 0 THEN
                    RAISE EXCEPTION 'cannot remove cat asset % with % existing memories', OLD.id, v_memory_count;
                END IF;
            END IF;

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute(f"""
        CREATE OR REPLACE FUNCTION trg_fn_cat_memories_validate_cat_asset()
        RETURNS TRIGGER AS $$
        DECLARE
            v_cat_id INTEGER;
        BEGIN
            SELECT cat_id INTO v_cat_id
            FROM {asset_table}
            WHERE id = NEW.{memory_asset_column};

            IF v_cat_id IS NULL THEN
                RAISE EXCEPTION '{memory_asset_column} % does not reference a cat asset (cat_id is NULL or row missing)', NEW.{memory_asset_column};
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)


def upgrade() -> None:
    op.rename_table("user_cats", "assets")

    constraint_renames = (
        ("user_cats_pkey", "assets_pkey"),
        ("user_cats_public_id_key", "assets_public_id_key"),
        ("user_cats_user_id_fkey", "assets_user_id_fkey"),
        ("user_cats_cat_id_fkey", "assets_cat_id_fkey"),
        ("user_cats_item_id_fkey", "assets_item_id_fkey"),
        ("uq_user_cats_user_cat", "uq_assets_user_cat"),
        ("uq_user_cats_user_item", "uq_assets_user_item"),
        ("ck_user_cats_cat_xor_item", "ck_assets_cat_xor_item"),
        ("ck_user_cats_quantity_positive", "ck_assets_quantity_positive"),
        ("ck_user_cats_cat_quantity_one", "ck_assets_cat_quantity_one"),
    )
    for old_name, new_name in constraint_renames:
        op.execute(f"ALTER TABLE assets RENAME CONSTRAINT {old_name} TO {new_name}")

    op.execute(
        "ALTER TRIGGER trg_user_cats_validate_reverse_references ON assets "
        "RENAME TO trg_assets_validate_reverse_references"
    )
    op.execute(
        "ALTER FUNCTION trg_fn_user_cats_validate_reverse_references() "
        "RENAME TO trg_fn_assets_validate_reverse_references"
    )

    _replace_asset_references(
        asset_table="assets",
        memory_asset_column="user_cat_id",
        reverse_function="trg_fn_assets_validate_reverse_references",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TRIGGER trg_assets_validate_reverse_references ON assets "
        "RENAME TO trg_user_cats_validate_reverse_references"
    )
    op.execute(
        "ALTER FUNCTION trg_fn_assets_validate_reverse_references() "
        "RENAME TO trg_fn_user_cats_validate_reverse_references"
    )

    reverse_constraint_renames = (
        ("assets_pkey", "user_cats_pkey"),
        ("assets_public_id_key", "user_cats_public_id_key"),
        ("assets_user_id_fkey", "user_cats_user_id_fkey"),
        ("assets_cat_id_fkey", "user_cats_cat_id_fkey"),
        ("assets_item_id_fkey", "user_cats_item_id_fkey"),
        ("uq_assets_user_cat", "uq_user_cats_user_cat"),
        ("uq_assets_user_item", "uq_user_cats_user_item"),
        ("ck_assets_cat_xor_item", "ck_user_cats_cat_xor_item"),
        ("ck_assets_quantity_positive", "ck_user_cats_quantity_positive"),
        ("ck_assets_cat_quantity_one", "ck_user_cats_cat_quantity_one"),
    )
    for old_name, new_name in reverse_constraint_renames:
        op.execute(f"ALTER TABLE assets RENAME CONSTRAINT {old_name} TO {new_name}")

    op.rename_table("assets", "user_cats")

    _replace_asset_references(
        asset_table="user_cats",
        memory_asset_column="user_cat_id",
        reverse_function="trg_fn_user_cats_validate_reverse_references",
    )
