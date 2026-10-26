"""Host-side operator commands.

Admins can only be created or removed here, by someone who already has shell access to the
host. There is deliberately no web endpoint that changes a role.

    docker compose run --rm api python -m alvo.cli create-admin --provider mock --subject NAME
"""

import argparse
import logging
import sys
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import sessionmaker

from alvo.identity.infrastructure import SqlIdentityStore
from alvo.shared.config import Settings
from alvo.shared.db import create_db_engine

audit = logging.getLogger("alvo.audit")


def _bounded(limit: int) -> Callable[[str], str]:
    def check(value: str) -> str:
        if not 0 < len(value) <= limit:
            raise argparse.ArgumentTypeError(f"must be 1 to {limit} characters")
        return value

    return check


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alvo.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("create-admin", "revoke-admin"):
        command = commands.add_parser(name)
        command.add_argument("--provider", required=True, type=_bounded(32))
        command.add_argument("--subject", required=True, type=_bounded(200))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = Settings()
    engine = create_db_engine(settings)
    try:
        with sessionmaker(engine)() as db:
            store = SqlIdentityStore(db)
            if args.command == "create-admin":
                store.get_or_create_user(args.provider, args.subject, datetime.now(UTC))
                store.set_role(args.provider, args.subject, "admin")
                db.commit()
                audit.warning("event=admin_created provider=%s", args.provider)
                print("Admin role set.")
                return 0
            changed = store.set_role(args.provider, args.subject, "user")
            db.commit()
            if not changed:
                print("No such user.", file=sys.stderr)
                return 1
            audit.warning("event=admin_revoked provider=%s", args.provider)
            print("Admin role removed.")
            return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
