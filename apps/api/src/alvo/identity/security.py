"""Session token and CSRF token primitives.

The browser holds a random bearer token; the database stores only a keyed hash, so a
database leak alone cannot be replayed as a session. Rotating `session_secret`
invalidates every session and CSRF token.
"""

import base64
import hashlib
import hmac
import json
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


def seal_flow_state(key: str, payload: dict[str, str | int]) -> str:
    """A tamper-proof cookie value for the short sign-in redirect (not encrypted).

    The browser holds `state`, `nonce` and the PKCE verifier between the redirect to the provider
    and the callback. The cookie is HttpOnly and signed, so it cannot be forged or altered.
    """
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    return f"{body}.{_flow_mac(key, body)}"


def open_flow_state(key: str, sealed: str) -> dict[str, str | int] | None:
    body, _, mac = sealed.partition(".")
    if not body or not hmac.compare_digest(mac.encode(), _flow_mac(key, body).encode()):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body.encode()))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _flow_mac(key: str, body: str) -> str:
    return hmac.new(key.encode(), b"oidc-flow:" + body.encode(), hashlib.sha256).hexdigest()
