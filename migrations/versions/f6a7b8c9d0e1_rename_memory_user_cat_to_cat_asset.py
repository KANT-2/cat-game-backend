"""rename cat memory user cat reference to cat asset

Revision ID: f6a7b8c9d0e1
Revises: e4f5a6b7c8d9
Create Date: 2026-09-03 18:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_memory_reference_functions(memory_column: str) -> None:
    op.execute(f"""
        CREATE OR REPLACE FUNCTION trg_fn_assets_validate_reverse_references()
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
                WHERE {memory_column} = OLD.id;

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
            FROM assets
            WHERE id = NEW.{memory_column};

            IF v_cat_id IS NULL THEN
                RAISE EXCEPTION '{memory_column} % does not reference a cat asset (cat_id is NULL or row missing)', NEW.{memory_column};
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)


def upgrade() -> None:
    op.alter_column(
        "cat_memories",
        "user_cat_id",
        new_column_name="cat_asset_id",
    )
    op.execute(
        "ALTER TABLE cat_memories RENAME CONSTRAINT "
        "cat_memories_user_cat_id_fkey TO cat_memories_cat_asset_id_fkey"
    )
    _replace_memory_reference_functions("cat_asset_id")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE cat_memories RENAME CONSTRAINT "
        "cat_memories_cat_asset_id_fkey TO cat_memories_user_cat_id_fkey"
    )
    op.alter_column(
        "cat_memories",
        "cat_asset_id",
        new_column_name="user_cat_id",
    )
    _replace_memory_reference_functions("user_cat_id")
