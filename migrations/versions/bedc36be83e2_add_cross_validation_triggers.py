"""add cross validation triggers

Revision ID: bedc36be83e2
Revises: 939a1af225c4
Create Date: 2026-09-01 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bedc36be83e2"
down_revision: str | Sequence[str] | None = "939a1af225c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    # ------------------------------------------------------------------
    # 1. trg_users_validate_surface_asset
    #    USERS.wallpaper_item_id / floor_item_id 가 실제 존재하는 아이템이고,
    #    카테고리가 맞고, 사용자가 실제로 보유(user_cats)한 아이템인지 검증
    # ------------------------------------------------------------------
    op.execute("""
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
                    SELECT 1 FROM user_cats
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
                    SELECT 1 FROM user_cats
                    WHERE user_id = NEW.id AND item_id = NEW.floor_item_id
                ) THEN
                    RAISE EXCEPTION 'user % does not own item % and cannot set it as floor', NEW.id, NEW.floor_item_id;
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_users_validate_surface_asset
        BEFORE INSERT OR UPDATE OF wallpaper_item_id, floor_item_id ON users
        FOR EACH ROW
        EXECUTE FUNCTION trg_fn_users_validate_surface_asset();
    """)

    # ------------------------------------------------------------------
    # 2. trg_task_attempts_validate_context_owner
    #    DAILY: attendance_task 소유자 == 제출자
    #    BATTLE: 제출자가 해당 room의 참가자인지
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION trg_fn_task_attempts_validate_context_owner()
        RETURNS TRIGGER AS $$
        DECLARE
            v_attendance_user_id INTEGER;
            v_room_id INTEGER;
            v_is_participant BOOLEAN;
        BEGIN
            IF NEW.context_type = 'DAILY' THEN
                SELECT a.user_id INTO v_attendance_user_id
                FROM attendance_tasks at
                JOIN attendances a ON a.id = at.attendance_id
                WHERE at.id = NEW.attendance_task_id;

                IF v_attendance_user_id IS NULL THEN
                    RAISE EXCEPTION 'attendance_task_id % does not resolve to a valid attendance owner', NEW.attendance_task_id;
                END IF;

                IF v_attendance_user_id <> NEW.user_id THEN
                    RAISE EXCEPTION 'user % cannot submit for attendance_task_id % owned by user %', NEW.user_id, NEW.attendance_task_id, v_attendance_user_id;
                END IF;
            END IF;

            IF NEW.context_type = 'BATTLE' THEN
                SELECT rt.room_id INTO v_room_id
                FROM room_tasks rt
                WHERE rt.id = NEW.room_task_id;

                IF v_room_id IS NULL THEN
                    RAISE EXCEPTION 'room_task_id % does not resolve to a valid room', NEW.room_task_id;
                END IF;

                SELECT EXISTS (
                    SELECT 1 FROM room_participants
                    WHERE room_id = v_room_id AND user_id = NEW.user_id
                ) INTO v_is_participant;

                IF NOT v_is_participant THEN
                    RAISE EXCEPTION 'user % is not a participant of room % for room_task_id %', NEW.user_id, v_room_id, NEW.room_task_id;
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_task_attempts_validate_context_owner
        BEFORE INSERT OR UPDATE ON task_attempts
        FOR EACH ROW
        EXECUTE FUNCTION trg_fn_task_attempts_validate_context_owner();
    """)

    # ------------------------------------------------------------------
    # 3. trg_placed_objects_validate_inventory
    #    아이템이 FURNITURE 카테고리이고, 보유 중이며,
    #    배치 개수가 보유 수량을 넘지 않는지 (행 잠금 후 검증)
    # ------------------------------------------------------------------
    op.execute("""
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
            FROM user_cats
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

    op.execute("""
        CREATE TRIGGER trg_placed_objects_validate_inventory
        BEFORE INSERT OR UPDATE ON placed_objects
        FOR EACH ROW
        EXECUTE FUNCTION trg_fn_placed_objects_validate_inventory();
    """)

    # ------------------------------------------------------------------
    # 4. trg_user_cats_validate_reverse_references
    #    보유 자산을 줄이거나 삭제할 때, 배치된 가구 수/현재 적용 중인
    #    벽지·바닥/연결된 고양이 기억과 충돌하지 않는지 검증
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION trg_fn_user_cats_validate_reverse_references()
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
                -- 관련 placed_objects 행을 먼저 잠근 뒤 개수 확인 (집계 함수와 FOR UPDATE는 같이 못 씀)
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
                WHERE user_cat_id = OLD.id;

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

    op.execute("""
        CREATE TRIGGER trg_user_cats_validate_reverse_references
        BEFORE UPDATE OR DELETE ON user_cats
        FOR EACH ROW
        EXECUTE FUNCTION trg_fn_user_cats_validate_reverse_references();
    """)

    # ------------------------------------------------------------------
    # 5. trg_cat_memories_validate_cat_asset
    #    CAT_MEMORIES.user_cat_id 가 실제 '고양이' 자산(cat_id NOT NULL)인지 검증
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION trg_fn_cat_memories_validate_cat_asset()
        RETURNS TRIGGER AS $$
        DECLARE
            v_cat_id INTEGER;
        BEGIN
            SELECT cat_id INTO v_cat_id FROM user_cats WHERE id = NEW.user_cat_id;

            IF v_cat_id IS NULL THEN
                RAISE EXCEPTION 'user_cat_id % does not reference a cat asset (cat_id is NULL or row missing)', NEW.user_cat_id;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_cat_memories_validate_cat_asset
        BEFORE INSERT OR UPDATE ON cat_memories
        FOR EACH ROW
        EXECUTE FUNCTION trg_fn_cat_memories_validate_cat_asset();
    """)


def downgrade() -> None:
    """Downgrade schema."""

    op.execute("DROP TRIGGER IF EXISTS trg_cat_memories_validate_cat_asset ON cat_memories;")
    op.execute("DROP FUNCTION IF EXISTS trg_fn_cat_memories_validate_cat_asset();")

    op.execute("DROP TRIGGER IF EXISTS trg_user_cats_validate_reverse_references ON user_cats;")
    op.execute("DROP FUNCTION IF EXISTS trg_fn_user_cats_validate_reverse_references();")

    op.execute("DROP TRIGGER IF EXISTS trg_placed_objects_validate_inventory ON placed_objects;")
    op.execute("DROP FUNCTION IF EXISTS trg_fn_placed_objects_validate_inventory();")

    op.execute("DROP TRIGGER IF EXISTS trg_task_attempts_validate_context_owner ON task_attempts;")
    op.execute("DROP FUNCTION IF EXISTS trg_fn_task_attempts_validate_context_owner();")

    op.execute("DROP TRIGGER IF EXISTS trg_users_validate_surface_asset ON users;")
    op.execute("DROP FUNCTION IF EXISTS trg_fn_users_validate_surface_asset();")
