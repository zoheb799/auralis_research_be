
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.db.base import Base
from app.db import models

# Alembic configuration
config = context.config

# Use the synchronous psycopg2 driver for Alembic migrations.
# The application can continue using asyncpg for async database access.
database_url = (
    settings.database_url
    .replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    .replace("postgresql+psycopg://", "postgresql+psycopg2://")
)

config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%"),
)

# Safe diagnostic: prints the driver only, never credentials.
print(
    "Alembic database driver:",
    make_url(config.get_main_option("sqlalchemy.url")).drivername,
)

# Configure logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for migrations
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""
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
    """Run migrations using a synchronous database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
