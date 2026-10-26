import os
import secrets
import shutil
from collections.abc import Iterator

import pytest
from testcontainers.community.postgres import PostgresContainer

# Same digest as compose.yaml so tests exercise the version we deploy.
POSTGRES_IMAGE = (
    "postgres:18-trixie@sha256:edb0c08dc33befd0262ab3b5cf1c4f3f8cfd8b09e88c05b45adee29d6761ddb6"
)


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    # Locally these tests skip without Docker; in CI a missing Docker must fail, not skip.
    if shutil.which("docker") is None and not os.environ.get("CI"):
        pytest.skip("docker not available")
    with PostgresContainer(
        POSTGRES_IMAGE,
        username="alvo_test",
        password=secrets.token_urlsafe(24),
        dbname="alvo_test",
        driver="psycopg",
    ) as postgres:
        yield postgres.get_connection_url()
