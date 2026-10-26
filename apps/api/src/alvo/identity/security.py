"""Session token and CSRF token primitives.

The browser holds a random bearer token; the database stores only a keyed hash, so a
database leak alone cannot be replayed as a session. Rotating `session_secret`
invalidates every session and CSRF token.
"""

import hashlib
import hmac
import secrets


def new_session_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits of entropy


def hash_session_token(key: str, token: str) -> str:
    return hmac.new(key.encode(), b"session:" + token.encode(), hashlib.sha256).hexdigest()


def csrf_token_for(key: str, session_hash: str) -> str:
    """Stateless CSRF token: unguessable without the server key and bound to one session."""
    return hmac.new(key.encode(), b"csrf:" + session_hash.encode(), hashlib.sha256).hexdigest()


def tokens_match(expected: str, presented: str) -> bool:
    return hmac.compare_digest(expected.encode(), presented.encode())
