import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from app.core.database import Base
from app.core.config import get_settings

# Import YOUR models
from app.modules.follows.models import Follow
from app.modules.notifications.models import Notification
from app.models.notification_preference import NotificationPreference

config = context.config
settings = get_settings()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

from sqlalchemy import Table, Column, String
Table("users", target_metadata, Column("id", String(36), primary_key=True), extend_existing=True)
Table("posts", target_metadata, Column("id", String(36), primary_key=True), extend_existing=True)

def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table":
        # Ignore teammates' tables explicitly
        if name in ("users", "posts", "comments", "likes"):
            return False
    return True

def run_migrations_offline() -> None:
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
