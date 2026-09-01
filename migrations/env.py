import logging
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.models.base import Base
from app.models.user import User
from app.models.concept import Concept
from app.models.item import Item
from app.models.cat import Cat
from app.models.attendance import Attendance
from app.models.attendance_task import AttendanceTask
from app.models.task import Task
from app.models.user_proficiency import UserProficiency
from app.models.room import Room
from app.models.room_participant import RoomParticipant
from app.models.room_task import RoomTask
from app.models.task_attempt import TaskAttempt
from app.models.placed_object import PlacedObject
from app.models.user_cat import UserCat
from app.models.gacha_execution import GachaExecution
from app.models.cat_memory import CatMemory

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, encoding="utf-8")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()