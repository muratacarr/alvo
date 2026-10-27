"""A fake Google for tests: real RSA signatures, no network."""

import json
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from alvo.identity.oidc import JWKS_URL, TOKEN_URL, GoogleOidc, OidcError

CLIENT_ID = "1234567890-abcdefghij.apps.googleusercontent.com"
REDIRECT_URI = "https://testserver/api/v1/auth/google/callback"
KID = "test-key-1"


def new_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeGoogle:
    """Serves the token and key endpoints. Tests set what the next ID token will say."""

    def __init__(self, key: rsa.RSAPrivateKey | None = None) -> None:
        self.key = key or new_key()
        self.subject = "google-sub-1"
        self.email = "invited@example.com"
        self.email_verified: Any = True
        self.nonce = ""
        self.issuer = "https://accounts.google.com"
        self.audience = CLIENT_ID
        self.expires_in = 3600
        self.signing_key: Any = self.key
        self.kid = KID
        self.algorithm = "RS256"
        self.fail_token_endpoint = False
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    def id_token(self) -> str:
        now = int(time.time())
        claims = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": self.subject,
            "iat": now,
            "exp": now + self.expires_in,
            "nonce": self.nonce,
            "email": self.email,
            "email_verified": self.email_verified,
        }
        return jwt.encode(
            claims, self.signing_key, algorithm=self.algorithm, headers={"kid": self.kid}
        )

    def fetch(self, url: str, form: dict[str, str] | None) -> dict[str, Any]:
        self.calls.append((url, form))
        if url == JWKS_URL:
            jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
            return {"keys": [{**jwk, "kid": KID, "alg": "RS256", "use": "sig"}]}
        if url == TOKEN_URL:
            if self.fail_token_endpoint:
                raise OidcError("provider request failed")
            return {"id_token": self.id_token(), "access_token": "unused"}
        raise OidcError("unexpected address")

    def client(self) -> GoogleOidc:
        return GoogleOidc(
            client_id=CLIENT_ID,
            client_secret="test-client-secret-value",  # noqa: S106
            redirect_uri=REDIRECT_URI,
            fetch=self.fetch,
        )
