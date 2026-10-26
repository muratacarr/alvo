from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest

from tests.integration.support import ORIGIN, Actor

P = "/api/v1/projects"


def create_project(actor: Actor, title: str = "HR Interview", **extra: Any) -> dict[str, Any]:
    response = actor.post(P, {"title": title, **extra})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def test_create_and_read_a_project(new_actor: Callable[[], Actor]) -> None:
    actor = new_actor()
    project = create_project(actor, description="Practice for interviews")
    assert project["title"] == "HR Interview"
    assert project["description"] == "Practice for interviews"
    assert project["archived"] is False
    assert "owner_id" not in project
    assert actor.get(f"{P}/{project['id']}").json() == project


def test_new_users_need_no_entitlement_for_free_content(new_actor: Callable[[], Actor]) -> None:
    assert create_project(new_actor())["id"]


def test_owner_is_taken_from_the_session_never_from_the_body(
    new_actor: Callable[[], Actor],
) -> None:
    actor = new_actor()
    for extra in (
        {"owner_id": str(uuid4())},
        {"id": str(uuid4())},
        {"archived": True},
        {"created_at": "2020-01-01T00:00:00Z"},
    ):
        assert actor.post(P, {"title": "x", **extra}).status_code == 422


def test_list_returns_only_own_projects_in_stable_order(
    new_actor: Callable[[], Actor],
) -> None:
    alice, bob = new_actor(), new_actor()
    first, second = create_project(alice, "A1"), create_project(alice, "A2")
    create_project(bob, "B1")
    listed = alice.get(P).json()
    assert [p["id"] for p in listed["items"]] == [first["id"], second["id"]]
    assert listed["next_cursor"] is None


def test_pagination_follows_the_cursor_without_gaps_or_repeats(
    new_actor: Callable[[], Actor],
) -> None:
    actor = new_actor()
    created = [create_project(actor, f"P{i}")["id"] for i in range(5)]
    seen: list[str] = []
    cursor: str | None = None
    while True:
        url = f"{P}?limit=2" + (f"&cursor={cursor}" if cursor else "")
        page = actor.get(url).json()
        seen += [p["id"] for p in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == created


def test_pagination_bounds_and_bad_cursor(new_actor: Callable[[], Actor]) -> None:
    actor = new_actor()
    assert actor.get(f"{P}?limit=101").status_code == 422
    assert actor.get(f"{P}?limit=0").status_code == 422
    bad = actor.get(f"{P}?cursor=garbage")
    assert bad.status_code == 422
    assert bad.json() == {"error": "invalid_cursor"}


def test_update_changes_only_allowed_fields(new_actor: Callable[[], Actor]) -> None:
    actor = new_actor()
    project = create_project(actor)
    updated = actor.patch(f"{P}/{project['id']}", {"title": "Backend Interview"})
    assert updated.status_code == 200
    assert updated.json()["title"] == "Backend Interview"
    assert updated.json()["id"] == project["id"]
    assert actor.patch(f"{P}/{project['id']}", {"owner_id": str(uuid4())}).status_code == 422


def test_archive_hides_from_default_list_and_unarchive_restores(
    new_actor: Callable[[], Actor],
) -> None:
    actor = new_actor()
    project = create_project(actor)
    assert actor.delete(f"{P}/{project['id']}").status_code == 204
    assert actor.get(P).json()["items"] == []
    shown = actor.get(f"{P}?include_archived=true").json()["items"]
    assert [p["id"] for p in shown] == [project["id"]]
    assert actor.get(f"{P}/{project['id']}").json()["archived"] is True
    assert actor.post(f"{P}/{project['id']}/unarchive").status_code == 200
    assert actor.get(f"{P}/{project['id']}").json()["archived"] is False


def test_archiving_twice_is_idempotent(new_actor: Callable[[], Actor]) -> None:
    actor = new_actor()
    project = create_project(actor)
    assert actor.delete(f"{P}/{project['id']}").status_code == 204
    assert actor.delete(f"{P}/{project['id']}").status_code == 204


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": ""},
        {"title": "x" * 201},
        {"title": "a\x00b"},
        {"title": 5},
        {"title": "ok", "description": "d" * 2001},
    ],
)
def test_invalid_project_payloads_are_rejected(
    new_actor: Callable[[], Actor], payload: dict[str, Any]
) -> None:
    assert new_actor().post(P, payload).status_code == 422


def test_unauthenticated_and_csrf_protection(new_actor: Callable[[], Actor]) -> None:
    actor = new_actor()
    actor.client.cookies.clear()
    assert actor.client.get(P).status_code == 401
    other = new_actor()
    no_csrf = other.client.post(P, json={"title": "x"}, headers=ORIGIN)
    assert no_csrf.status_code == 403


def test_html_is_stored_verbatim_and_served_as_json_text(
    new_actor: Callable[[], Actor],
) -> None:
    actor = new_actor()
    payload = "<script>alert(1)</script>"
    project = create_project(actor, payload)
    response = actor.get(f"{P}/{project['id']}")
    assert response.json()["title"] == payload
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["x-content-type-options"] == "nosniff"
