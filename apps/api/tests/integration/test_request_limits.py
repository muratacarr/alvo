from collections.abc import Callable

from tests.integration.support import ORIGIN, Actor


def test_oversized_bodies_are_rejected_before_processing(
    new_actor: Callable[[], Actor],
) -> None:
    actor = new_actor()
    huge = {"title": "x", "description": "d" * (2 * 1024 * 1024)}
    response = actor.post("/api/v1/projects", huge)
    assert response.status_code == 413
    assert response.json() == {"error": "payload_too_large"}


def test_oversized_bodies_without_content_length_are_also_rejected(
    new_actor: Callable[[], Actor],
) -> None:
    actor = new_actor()

    def chunks() -> "list[bytes]":
        return [b'{"title":"x","description":"' + b"d" * 65536] + [b"d" * 65536] * 40 + [b'"}']

    response = actor.client.post(
        "/api/v1/projects",
        content=iter(chunks()),
        headers={**ORIGIN, "X-CSRF-Token": actor.csrf, "Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_validation_errors_do_not_echo_the_submitted_values(
    new_actor: Callable[[], Actor],
) -> None:
    actor = new_actor()
    secret_looking = "SuperSecretValue123"
    response = actor.post("/api/v1/projects", {"title": "x", "owner_id": secret_looking})
    assert response.status_code == 422
    assert secret_looking not in response.text
    assert response.json()["error"] == "invalid_request"
    assert "body.owner_id" in response.json()["fields"]


def test_malformed_json_is_a_generic_422(new_actor: Callable[[], Actor]) -> None:
    actor = new_actor()
    response = actor.client.post(
        "/api/v1/projects",
        content=b"{not json",
        headers={**ORIGIN, "X-CSRF-Token": actor.csrf, "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"
