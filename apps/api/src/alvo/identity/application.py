"""Identity use cases: sign in, authenticate a request, sign out.

Providers (the development mock now, an OIDC adapter later) only produce a
`VerifiedIdentity`; everything after that is provider-agnostic.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from alvo.identity.domain import Principal, SessionPolicy, VerifiedIdentity
from alvo.identity.infrastructure import SqlIdentityStore
from alvo.identity.security import csrf_token_for, hash_session_token, new_session_token

audit = logging.getLogger("alvo.audit")

# Avoid a write on every request: refresh the idle clock at most once a minute.
_TOUCH_INTERVAL = timedelta(seconds=60)


@dataclass(frozen=True)
class SignedIn:
    user_id: UUID
    token: str
    csrf_token: str


@dataclass(frozen=True)
class AuthenticatedSession:
    principal: Principal
    csrf_token: str


class IdentityService:
    def __init__(self, secret: str, policy: SessionPolicy, clock: Callable[[], datetime]) -> None:
        self._secret = secret
        self._policy = policy
        self._clock = clock

    def sign_in(
        self, db: Session, identity: VerifiedIdentity, presented_token: str | None
    ) -> SignedIn:
        now = self._clock()
        store = SqlIdentityStore(db)
        # Rotation: a session presented at login is revoked and never reused (anti-fixation).
        if presented_token:
            previous = store.find_session(hash_session_token(self._secret, presented_token))
            if previous:
                store.revoke(previous.id, now)
        user_id = store.get_or_create_user(identity.provider, identity.subject, now)
        token = new_session_token()
        token_hash = hash_session_token(self._secret, token)
        store.create_session(user_id, token_hash, now)
        db.commit()
        audit.info("event=login user_id=%s provider=%s", user_id, identity.provider)
        return SignedIn(user_id, token, csrf_token_for(self._secret, token_hash))

    def authenticate(self, db: Session, token: str) -> AuthenticatedSession | None:
        now = self._clock()
        store = SqlIdentityStore(db)
        token_hash = hash_session_token(self._secret, token)
        session = store.find_session(token_hash)
        if session is None or not self._policy.is_active(session, now):
            return None
        if now - session.last_seen_at >= _TOUCH_INTERVAL:
            store.touch(session.id, now)
            db.commit()
        return AuthenticatedSession(
            Principal(session.user_id), csrf_token_for(self._secret, token_hash)
        )

    def sign_out(self, db: Session, token: str) -> None:
        now = self._clock()
        store = SqlIdentityStore(db)
        session = store.find_session(hash_session_token(self._secret, token))
        if session is None:
            return
        store.revoke(session.id, now)
        db.commit()
        audit.info("event=logout user_id=%s", session.user_id)
