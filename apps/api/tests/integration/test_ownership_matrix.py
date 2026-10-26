"""Two-user authorization matrix: user B must never read or change user A's content."""

from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from tests.integration.support import Actor
from tests.integration.test_content_api import World

P = "/api/v1/projects"
Call = tuple[str, str, dict[str, Any] | None]


def foreign_calls(w: World) -> list[Call]:
    base, m, t, i = w.base, w.module["id"], w.topic["id"], w.item["id"]
    item_payload = w.item_payload(prompt="hijack")
    return [
        ("GET", base, None),
        ("PATCH", base, {"title": "hijack"}),
        ("DELETE", base, None),
        ("POST", f"{base}/unarchive", None),
        ("GET", f"{base}/modules", None),
        ("POST", f"{base}/modules", {"title": "hijack"}),
        ("GET", f"{base}/modules/{m}", None),
        ("PATCH", f"{base}/modules/{m}", {"title": "hijack"}),
        ("DELETE", f"{base}/modules/{m}", None),
        ("GET", f"{base}/topics", None),
        ("POST", f"{base}/topics", {"module_id": m, "title": "hijack"}),
        ("GET", f"{base}/topics/{t}", None),
        ("PATCH", f"{base}/topics/{t}", {"title": "hijack"}),
        ("DELETE", f"{base}/topics/{t}", None),
        ("GET", f"{base}/items", None),
        ("POST", f"{base}/items", item_payload),
        ("GET", f"{base}/items/{i}", None),
        ("PATCH", f"{base}/items/{i}", {"prompt": "hijack"}),
        ("DELETE", f"{base}/items/{i}", None),
    ]


def send(actor: Actor, call: Call) -> Any:
    method, path, body = call
    if method == "GET":
        return actor.get(path)
    if method == "DELETE":
        return actor.delete(path)
    if method == "PATCH":
        return actor.patch(path, body)
    return actor.post(path, body)


@pytest.fixture
def pair(new_actor: Callable[[], Actor]) -> tuple[World, Actor]:
    return World(new_actor()), new_actor()


def test_every_foreign_endpoint_returns_a_uniform_404(pair: tuple[World, Actor]) -> None:
    world, intruder = pair
    for call in foreign_calls(world):
        response = send(intruder, call)
        assert response.status_code == 404, call
        assert response.json() == {"error": "not_found"}, call


def test_foreign_requests_change_nothing(pair: tuple[World, Actor]) -> None:
    world, intruder = pair
    before = {
        "project": world.actor.get(world.base).json(),
        "module": world.actor.get(f"{world.base}/modules/{world.module['id']}").json(),
        "topic": world.actor.get(f"{world.base}/topics/{world.topic['id']}").json(),
        "item": world.actor.get(f"{world.base}/items/{world.item['id']}").json(),
    }
    for call in foreign_calls(world):
        send(intruder, call)
    assert world.actor.get(world.base).json() == before["project"]
    assert world.actor.get(f"{world.base}/modules/{world.module['id']}").json() == before["module"]
    assert world.actor.get(f"{world.base}/topics/{world.topic['id']}").json() == before["topic"]
    assert world.actor.get(f"{world.base}/items/{world.item['id']}").json() == before["item"]
    assert world.actor.get(f"{world.base}/items").json()["items"][0]["prompt"] == (
        "Tell me about yourself."
    )


def test_lists_never_leak_other_users_rows(pair: tuple[World, Actor]) -> None:
    world, intruder = pair
    assert intruder.get(P).json()["items"] == []
    assert intruder.get(f"{P}?include_archived=true").json()["items"] == []


def test_not_found_looks_identical_for_foreign_and_nonexistent_ids(
    pair: tuple[World, Actor],
) -> None:
    world, intruder = pair
    foreign = intruder.get(world.base)
    missing = intruder.get(f"{P}/{uuid4()}")
    assert (foreign.status_code, foreign.json()) == (missing.status_code, missing.json())


def test_intruder_cannot_attach_their_content_to_foreign_parents(
    pair: tuple[World, Actor],
) -> None:
    world, intruder = pair
    own = intruder.post(P, {"title": "mine"}).json()
    base = f"{P}/{own['id']}"
    assert (
        intruder.post(f"{base}/topics", {"module_id": world.module["id"], "title": "x"}).status_code
        == 404
    )
    assert (
        intruder.post(f"{base}/items", world.item_payload(topic_id=world.topic["id"])).status_code
        == 404
    )


def test_the_database_itself_rejects_cross_project_references(
    pair: tuple[World, Actor], migrated_database_url: str
) -> None:
    world, _ = pair
    other = world.actor.post(P, {"title": "other"}).json()
    engine = create_engine(migrated_database_url)
    try:
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO topics (id, project_id, module_id, title, created_at, "
                    "updated_at) VALUES (:i, :p, :m, 't', now(), now())"
                ),
                {"i": uuid4(), "p": other["id"], "m": world.module["id"]},
            )
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO learning_items (id, project_id, topic_id, type, prompt, "
                    "created_at, updated_at) VALUES (:i, :p, :t, 'question', 'q', now(), now())"
                ),
                {"i": uuid4(), "p": other["id"], "t": world.topic["id"]},
            )
    finally:
        engine.dispose()
