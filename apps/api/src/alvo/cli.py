"""Host-side operator commands.

Admins can only be created or removed here, by someone who already has shell access to the
host. There is deliberately no web endpoint that changes a role.

    docker compose run --rm api python -m alvo.cli create-admin --provider mock --subject NAME

With Google sign-in, registration is by invitation only. An invitation names an email address,
expires, and is used up at that person's first sign-in:

    python -m alvo.cli invite --email someone@example.com [--admin] [--days 14]
    python -m alvo.cli revoke-invite --email someone@example.com
"""

import argparse
import logging
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import sessionmaker

from alvo.identity.domain import Role
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


_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_MAX_EMAIL_LENGTH = 254
_MAX_INVITE_DAYS = 90


def _email(value: str) -> str:
    # Lower-cased because the sign-in compares against Google's lower-cased address. Gmail
    # dots and "+" tags are NOT normalised: invite the address exactly as the account has it.
    email = value.strip().lower()
    if len(email) > _MAX_EMAIL_LENGTH or not _EMAIL.fullmatch(email):
        raise argparse.ArgumentTypeError("not a valid email address")
    return email


def _days(value: str) -> int:
    try:
        days = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a whole number") from exc
    if not 1 <= days <= _MAX_INVITE_DAYS:
        raise argparse.ArgumentTypeError(f"must be 1 to {_MAX_INVITE_DAYS}")
    return days


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alvo.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("create-admin", "revoke-admin"):
        command = commands.add_parser(name)
        command.add_argument("--provider", required=True, type=_bounded(32))
        command.add_argument("--subject", required=True, type=_bounded(200))
    invite = commands.add_parser("invite")
    invite.add_argument("--email", required=True, type=_email)
    invite.add_argument("--admin", action="store_true")
    invite.add_argument("--days", type=_days, default=14)
    revoke_invite = commands.add_parser("revoke-invite")
    revoke_invite.add_argument("--email", required=True, type=_email)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = Settings()
    engine = create_db_engine(settings)
    try:
        with sessionmaker(engine)() as db:
            store = SqlIdentityStore(db)
            if args.command == "invite":
                now = datetime.now(UTC)
                role: Role = "admin" if args.admin else "user"
                store.upsert_invite(args.email, role, now, now + timedelta(days=args.days))
                db.commit()
                audit.warning("event=invite_created role=%s days=%s", role, args.days)
                print(f"Invitation saved for {args.email} (role {role}, valid {args.days} days).")
                return 0
            if args.command == "revoke-invite":
                removed = store.revoke_invite(args.email)
                db.commit()
                if not removed:
                    print("No such invitation.", file=sys.stderr)
                    return 1
                audit.warning("event=invite_revoked")
                print("Invitation removed.")
                return 0
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
