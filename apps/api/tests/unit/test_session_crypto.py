import secrets

from alvo.identity.security import csrf_token_for, hash_session_token, new_session_token

KEY = secrets.token_urlsafe(48)


def test_tokens_are_long_and_unique() -> None:
    first, second = new_session_token(), new_session_token()
    assert first != second
    assert len(first) >= 43  # 256 bits, url-safe base64


def test_hash_is_deterministic_and_not_the_token() -> None:
    token = new_session_token()
    assert hash_session_token(KEY, token) == hash_session_token(KEY, token)
    assert hash_session_token(KEY, token) != token
    assert token not in hash_session_token(KEY, token)


def test_hash_depends_on_the_server_secret() -> None:
    token = new_session_token()
    assert hash_session_token(KEY, token) != hash_session_token(secrets.token_urlsafe(48), token)


def test_csrf_token_is_bound_to_the_session() -> None:
    first = hash_session_token(KEY, new_session_token())
    second = hash_session_token(KEY, new_session_token())
    assert csrf_token_for(KEY, first) == csrf_token_for(KEY, first)
    assert csrf_token_for(KEY, first) != csrf_token_for(KEY, second)


def test_csrf_token_is_not_the_session_hash() -> None:
    session_hash = hash_session_token(KEY, new_session_token())
    assert csrf_token_for(KEY, session_hash) != session_hash
