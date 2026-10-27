"""Google sign-in (OpenID Connect, authorization code flow with PKCE).

This module only turns a Google redirect into verified claims; sessions, invitations and roles
are handled elsewhere. Network access goes through an injected `Fetch` function so tests never
touch the internet. Only the three fixed Google endpoints below can ever be contacted.

Checks on the ID token: RS256 signature against Google's published keys, issuer, audience (our
client id), expiry, the `nonce` we sent, and a verified email address.
"""

import base64
import hashlib
import json
import secrets
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jwt

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105  (a URL, not a credential)
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
_ALLOWED_URLS = {TOKEN_URL, JWKS_URL}
_TIMEOUT_SECONDS = 5
_MAX_RESPONSE_BYTES = 256 * 1024
_JWKS_TTL_SECONDS = 3600
_LEEWAY_SECONDS = 30
_MAX_EMAIL_LENGTH = 254

# (url, form) -> parsed JSON. `form` is None for GET and the POST body otherwise.
Fetch = Callable[[str, dict[str, str] | None], dict[str, Any]]


class OidcError(Exception):
    """Anything wrong with the provider's answer. The message is for logs, never for users."""


@dataclass(frozen=True)
class FlowStart:
    url: str
    state: str
    nonce: str
    verifier: str


@dataclass(frozen=True)
class GoogleClaims:
    subject: str
    email: str


def fetch_json(url: str, form: dict[str, str] | None) -> dict[str, Any]:
    """Real network access: fixed https URLs only, short timeout, bounded response."""
    if url not in _ALLOWED_URLS:
        raise OidcError("refusing to contact an unexpected address")
    data = urllib.parse.urlencode(form).encode() if form is not None else None
    request = urllib.request.Request(url, data=data)  # noqa: S310  (https URL from the allow-list)
    request.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except OSError as exc:
        raise OidcError("provider request failed") from exc
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise OidcError("provider response too large")
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise OidcError("provider response is not JSON") from exc
    if not isinstance(parsed, dict):
        raise OidcError("provider response has an unexpected shape")
    return parsed


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class GoogleOidc:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        fetch: Fetch = fetch_json,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._fetch = fetch
        self._monotonic = monotonic
        self._jwks: jwt.PyJWKSet | None = None
        self._jwks_loaded_at = 0.0

    def begin(self) -> FlowStart:
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(48)  # 64 characters, within RFC 7636's 43 to 128
        query = urllib.parse.urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "response_type": "code",
                "scope": "openid email",
                "state": state,
                "nonce": nonce,
                "code_challenge": _b64url(hashlib.sha256(verifier.encode()).digest()),
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
        return FlowStart(f"{AUTH_URL}?{query}", state, nonce, verifier)

    def complete(self, code: str, verifier: str, nonce: str) -> GoogleClaims:
        tokens = self._fetch(
            TOKEN_URL,
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self._redirect_uri,
            },
        )
        id_token = tokens.get("id_token")
        if not isinstance(id_token, str):
            raise OidcError("no id_token in the token response")
        return self._verify(id_token, nonce)

    def _signing_key(self, kid: str) -> jwt.PyJWK:
        for refresh in (False, True):
            stale = self._monotonic() - self._jwks_loaded_at > _JWKS_TTL_SECONDS
            if self._jwks is None or stale or refresh:
                self._jwks = jwt.PyJWKSet.from_dict(self._fetch(JWKS_URL, None))
                self._jwks_loaded_at = self._monotonic()
            for key in self._jwks.keys:
                if key.key_id == kid:
                    return key
        raise OidcError("unknown signing key")

    def _verify(self, id_token: str, nonce: str) -> GoogleClaims:
        try:
            header = jwt.get_unverified_header(id_token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise OidcError("unexpected token header")
            claims = jwt.decode(
                id_token,
                self._signing_key(header["kid"]).key,
                algorithms=["RS256"],
                audience=self._client_id,
                leeway=_LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise OidcError(f"id_token rejected: {type(exc).__name__}") from exc

        if claims["iss"] not in _ISSUERS:
            raise OidcError("wrong issuer")
        if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise OidcError("nonce mismatch")
        email = claims.get("email")
        if claims.get("email_verified") not in (True, "true") or not isinstance(email, str):
            raise OidcError("no verified email")
        email = email.strip().lower()
        subject = claims["sub"]
        if not email or len(email) > _MAX_EMAIL_LENGTH or not isinstance(subject, str):
            raise OidcError("malformed claims")
        return GoogleClaims(subject=subject, email=email)
