from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

import alvo.entitlements.infrastructure  # noqa: F401  (registers tables on the metadata)
import alvo.identity.infrastructure  # noqa: F401
from alvo.shared.config import Settings
from alvo.shared.orm import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Each module's persistence layer is imported above so its tables register on this metadata.
target_metadata = Base.metadata


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
