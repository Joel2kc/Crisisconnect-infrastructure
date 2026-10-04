from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from dotenv import load_dotenv
from sqlmodel import SQLModel

from alembic import context

# Load the project configuration before Alembic reads the database URL.
load_dotenv()

# Import model modules here for 'autogenerate' support. Add every new model
# module to this section so its table is registered with SQLModel.metadata.

# e.g from db.schema import mymodel
# from db.schemas import user
from db.models import (
    user_model,
    agency_model,
    refresh_token,
    password_reset,
    verify_email,
    volunteer_model,
    incident_model,
    ai_model,
    resource_model,
    location_model,
    volunteer_assignment_model,
    incident_model,
    emergency_categories,
    emergency_contact,
    responder_model,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL is not configured. Add it to .env or export it before "
        "running an Alembic command."
    )

# Keep credentials out of alembic.ini and use the same URL as the application.
# The '%' is doubled because Alembic stores this in a configparser, where '%'
# begins an interpolation token. A password containing a percent-encoded
# character (e.g. '@' written as '%40') would otherwise raise
# "invalid interpolation syntax". create_engine() in db/database.py takes the
# raw URL and needs no such escaping.
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
