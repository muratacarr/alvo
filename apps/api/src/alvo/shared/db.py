"""Database engine construction and the readiness probe.

Only connection plumbing lives here; persistence for business modules belongs
in each module's infrastructure layer.
"""

import logging
from collections.abc import Callable

from sqlalchemy import Engine, create_engine, text

from alvo.shared.config import Settings

logger = logging.getLogger("alvo.db")

_CONNECT_TIMEOUT_SECONDS = 2


def create_db_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": _CONNECT_TIMEOUT_SECONDS},
    )


def make_readiness_probe(engine: Engine) -> Callable[[], bool]:
    def probe() -> bool:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:
            # Log only the exception type: driver messages can contain hosts or credentials.
            logger.warning("database_not_ready error_type=%s", type(exc).__name__)
            return False
        return True

    return probe
