import base64
import hashlib
import urllib.parse

import jwt
import pytest

from alvo.identity.oidc import AUTH_URL, JWKS_URL, TOKEN_URL, OidcError, fetch_json
from alvo.identity.security import open_flow_state, seal_flow_state
from tests.oidc_support import CLIENT_ID, REDIRECT_URI, FakeGoogle, new_key

VERIFIER = "v" * 64
NONCE = "n-1"


def complete(google: FakeGoogle) -> tuple[str, str]:
    google.nonce = NONCE
    claims = google.client().complete("auth-code", VERIFIER, NONCE)
    return claims.subject, claims.email


def test_a_valid_token_yields_subject_and_lowercased_email() -> None:
    google = FakeGoogle()
    google.email = "  Invited@Example.COM "
    assert complete(google) == ("google-sub-1", "invited@example.com")


def test_the_authorization_url_uses_pkce_state_nonce_and_minimal_scope() -> None:
    flow = FakeGoogle().client().begin()
    url = urllib.parse.urlsplit(flow.url)
    query = dict(urllib.parse.parse_qsl(url.query))
    assert f"{url.scheme}://{url.netloc}{url.path}" == AUTH_URL
    assert query["client_id"] == CLIENT_ID
    assert query["redirect_uri"] == REDIRECT_URI
    assert query["response_type"] == "code"
    assert query["scope"] == "openid email"
    assert query["state"] == flow.state and query["nonce"] == flow.nonce
    assert query["code_challenge_method"] == "S256"
    digest = hashlib.sha256(flow.verifier.encode()).digest()
    assert query["code_challenge"] == base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    assert len(flow.verifier) >= 43
    assert "client_secret" not in query


def test_each_flow_gets_fresh_random_values() -> None:
    client = FakeGoogle().client()
    first, second = client.begin(), client.begin()
    assert {first.state, first.nonce, first.verifier}.isdisjoint(
        {second.state, second.nonce, second.verifier}
    )


def test_the_code_and_verifier_are_sent_to_the_token_endpoint_only() -> None:
    google = FakeGoogle()
    complete(google)
    url, form = google.calls[0]
    assert url == TOKEN_URL and form is not None
    assert form["code"] == "auth-code" and form["code_verifier"] == VERIFIER
    assert form["grant_type"] == "authorization_code"
    assert [u for u, _ in google.calls] == [TOKEN_URL, JWKS_URL]


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("nonce", "someone-elses-nonce"),
        ("audience", "another-app.apps.googleusercontent.com"),
        ("issuer", "https://evil.example.com"),
        ("expires_in", -3600),
        ("email_verified", False),
        ("email_verified", "false"),
        ("email", ""),
        ("kid", "unknown-key"),
    ],
)
def test_bad_tokens_are_rejected(attribute: str, value: object) -> None:
    google = FakeGoogle()
    setattr(google, attribute, value)
    # The flow expects NONCE; the "nonce" case makes Google answer with another one.
    if attribute != "nonce":
        google.nonce = NONCE
    with pytest.raises(OidcError):
        google.client().complete("auth-code", VERIFIER, NONCE)


def test_a_token_signed_with_a_shared_secret_algorithm_is_rejected() -> None:
    google = FakeGoogle()
    google.signing_key = "symmetric-secret-that-is-long-enough-for-hs256"
    google.algorithm = "HS256"
    google.nonce = NONCE
    with pytest.raises(OidcError):
        google.client().complete("auth-code", VERIFIER, NONCE)


def test_a_token_signed_by_another_key_is_rejected() -> None:
    google = FakeGoogle()
    google.signing_key = new_key()
    google.nonce = NONCE
    with pytest.raises(OidcError):
        google.client().complete("auth-code", VERIFIER, NONCE)


def test_the_unsigned_none_algorithm_is_rejected() -> None:
    google = FakeGoogle()
    forged = jwt.encode(
        {
            "iss": "https://accounts.google.com",
            "aud": CLIENT_ID,
            "sub": "x",
            "iat": 1,
            "exp": 9**10,
        },
        key=None,  # type: ignore[arg-type]
        algorithm="none",
        headers={"kid": "test-key-1"},
    )
    google.id_token = lambda: forged  # type: ignore[method-assign]
    with pytest.raises(OidcError):
        google.client().complete("auth-code", VERIFIER, NONCE)


def test_a_provider_failure_is_an_error() -> None:
    google = FakeGoogle()
    google.fail_token_endpoint = True
    with pytest.raises(OidcError):
        google.client().complete("auth-code", VERIFIER, NONCE)


def test_signing_keys_are_cached_between_sign_ins() -> None:
    google = FakeGoogle()
    client = google.client()
    google.nonce = NONCE
    client.complete("c1", VERIFIER, NONCE)
    client.complete("c2", VERIFIER, NONCE)
    assert [u for u, _ in google.calls].count(JWKS_URL) == 1


def test_the_real_fetcher_only_contacts_the_fixed_google_addresses() -> None:
    with pytest.raises(OidcError):
        fetch_json("https://evil.example.com/token", {"a": "b"})
    with pytest.raises(OidcError):
        fetch_json("http://169.254.169.254/latest/meta-data", None)


def test_flow_state_is_signed_and_detects_tampering() -> None:
    sealed = seal_flow_state("k" * 40, {"s": "state", "e": 5})
    assert open_flow_state("k" * 40, sealed) == {"s": "state", "e": 5}
    assert open_flow_state("other-key" * 5, sealed) is None
    body, _, mac = sealed.partition(".")
    assert open_flow_state("k" * 40, f"{body}x.{mac}") is None
    assert open_flow_state("k" * 40, "garbage") is None
    assert open_flow_state("k" * 40, "") is None
