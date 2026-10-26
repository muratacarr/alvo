from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from alvo.shared.config import Settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# No business tables yet; modules will register their metadata here.
target_metadata = None


def _database_url() -> str:
    return Settings().database_url.get_secret_value()


def run_migrations_offline() -> None:
    context.configure(url=_database_url(), literal_binds=True, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
