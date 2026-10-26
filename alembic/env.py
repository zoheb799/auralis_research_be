
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401


# Alembic configuration
config = context.config


def get_sync_database_url() -> str:
    """Convert the application database URL for synchronous Alembic use."""

    database_url = settings.database_url.replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg2://",
        1,
    ).replace(
        "postgresql+psycopg://",
        "postgresql+psycopg2://",
        1,
    )

    parsed_url = make_url(database_url)

    # Normalize plain PostgreSQL URLs to use psycopg2.
    if parsed_url.drivername == "postgresql":
        parsed_url = parsed_url.set(drivername="postgresql+psycopg2")

    # asyncpg uses ssl=require; psycopg2 uses sslmode=require.
    query = dict(parsed_url.query)

    if "ssl" in query:
        query["sslmode"] = query.pop("ssl")

    # This option is not needed for psycopg2.
    query.pop("channel_binding", None)

    parsed_url = parsed_url.set(query=query)

    return parsed_url.render_as_string(hide_password=False)


database_url = get_sync_database_url()

config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%"),
)

# Print the driver only; never print credentials.
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
    """Run migrations without opening a database connection."""

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

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
