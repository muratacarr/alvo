from fastapi import Request

from alvo.shared.http import client_address


def request(forwarded: str | None, peer: str = "10.0.0.5") -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded is not None else []
    return Request(
        {"type": "http", "headers": headers, "client": (peer, 1234), "method": "GET", "path": "/"}
    )


def test_the_header_is_ignored_unless_trusted() -> None:
    assert client_address(request("203.0.113.9"), trust_forwarded_for=False) == "10.0.0.5"


def test_the_last_entry_wins_so_a_client_cannot_prepend_a_fake_address() -> None:
    forged = request("1.2.3.4, 203.0.113.9")
    assert client_address(forged, trust_forwarded_for=True) == "203.0.113.9"


def test_garbage_falls_back_to_the_socket_peer() -> None:
    assert client_address(request("not-an-ip"), trust_forwarded_for=True) == "10.0.0.5"
    assert client_address(request(None), trust_forwarded_for=True) == "10.0.0.5"
