from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest

from tests.integration.support import Actor

P = "/api/v1/projects"


class World:
    """project -> module -> topic -> item, created by one actor."""

    def __init__(self, actor: Actor) -> None:
        self.actor = actor
        self.project = self._ok(actor.post(P, {"title": "HR"}))
        self.base = f"{P}/{self.project['id']}"
        self.module = self._ok(actor.post(f"{self.base}/modules", {"title": "Basics"}))
        self.topic = self._ok(
            actor.post(f"{self.base}/topics", {"module_id": self.module["id"], "title": "Intro"})
        )
        self.item = self._ok(actor.post(f"{self.base}/items", self.item_payload()))

    @staticmethod
    def _ok(response: Any) -> dict[str, Any]:
        assert response.status_code == 201, response.text
        body: dict[str, Any] = response.json()
        return body

    def item_payload(self, **overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "topic_id": self.topic["id"] if hasattr(self, "topic") else None,
            "type": "question",
            "prompt": "Tell me about yourself.",
        }
        payload.update(overrides)
        return payload


@pytest.fixture
def world(new_actor: Callable[[], Actor]) -> World:
    return World(new_actor())


def test_hierarchy_is_created_and_readable(world: World) -> None:
    a, b = world.actor, world.base
    assert a.get(f"{b}/modules/{world.module['id']}").json()["title"] == "Basics"
    assert a.get(f"{b}/topics/{world.topic['id']}").json()["module_id"] == world.module["id"]
    item = a.get(f"{b}/items/{world.item['id']}").json()
    assert item["topic_id"] == world.topic["id"]
    assert item["type"] == "question"
    assert item["keywords"] == [] and item["tags"] == [] and item["follow_up_questions"] == []


def test_full_item_fields_round_trip(world: World) -> None:
    payload = world.item_payload(
        type="phrase",
        prompt="break the ice",
        sample_answer="To start a conversation.",
        translation="buzları eritmek",
        keywords=["icebreaker", "social"],
        tags=["idiom"],
        follow_up_questions=["Can you use it in a sentence?"],
        difficulty=2,
    )
    created = world.actor.post(f"{world.base}/items", payload).json()
    fetched = world.actor.get(f"{world.base}/items/{created['id']}").json()
    for key, value in payload.items():
        assert fetched[key] == value, key


def test_item_update_and_archive(world: World) -> None:
    url = f"{world.base}/items/{world.item['id']}"
    updated = world.actor.patch(url, {"sample_answer": "I am a backend developer."})
    assert updated.json()["sample_answer"] == "I am a backend developer."
    assert updated.json()["prompt"] == "Tell me about yourself."
    assert world.actor.delete(url).status_code == 204
    listing = world.actor.get(f"{world.base}/items?topic_id={world.topic['id']}").json()
    assert listing["items"] == []
    shown = world.actor.get(
        f"{world.base}/items?topic_id={world.topic['id']}&include_archived=true"
    ).json()
    assert [i["id"] for i in shown["items"]] == [world.item["id"]]


def test_listing_filters_by_parent_and_paginates_stably(world: World) -> None:
    for n in range(4):
        world.actor.post(f"{world.base}/items", world.item_payload(prompt=f"Q{n}"))
    first = world.actor.get(f"{world.base}/items?limit=2").json()
    second = world.actor.get(f"{world.base}/items?limit=2&cursor={first['next_cursor']}").json()
    ids = [i["id"] for i in first["items"] + second["items"]]
    assert len(ids) == len(set(ids)) == 4
    other_topic = world.actor.post(
        f"{world.base}/topics", {"module_id": world.module["id"], "title": "Other"}
    ).json()
    assert world.actor.get(f"{world.base}/items?topic_id={other_topic['id']}").json()["items"] == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"type": "essay"},
        {"prompt": ""},
        {"prompt": "x" * 2001},
        {"prompt": "a\x00b"},
        {"sample_answer": "x" * 10001},
        {"keywords": ["k"] * 31},
        {"keywords": ["x" * 65]},
        {"tags": [""]},
        {"follow_up_questions": ["q"] * 11},
        {"difficulty": 0},
        {"difficulty": 6},
        {"owner_id": "x"},
        {"project_id": "x"},
    ],
)
def test_invalid_item_payloads_are_rejected(world: World, overrides: dict[str, Any]) -> None:
    response = world.actor.post(f"{world.base}/items", world.item_payload(**overrides))
    assert response.status_code == 422


def test_items_cannot_be_created_under_an_archived_topic_or_project(world: World) -> None:
    world.actor.delete(f"{world.base}/topics/{world.topic['id']}")
    blocked = world.actor.post(f"{world.base}/items", world.item_payload())
    assert blocked.status_code == 409
    assert blocked.json() == {"error": "archived"}
    world.actor.delete(world.base)
    assert world.actor.post(f"{world.base}/modules", {"title": "x"}).status_code == 409
    assert (
        world.actor.patch(f"{world.base}/items/{world.item['id']}", {"prompt": "z"}).status_code
        == 409
    )


def test_topics_and_items_can_move_within_the_same_project(world: World) -> None:
    other_module = world.actor.post(f"{world.base}/modules", {"title": "Advanced"}).json()
    moved = world.actor.patch(
        f"{world.base}/topics/{world.topic['id']}", {"module_id": other_module["id"]}
    )
    assert moved.json()["module_id"] == other_module["id"]
    other_topic = world.actor.post(
        f"{world.base}/topics", {"module_id": other_module["id"], "title": "T2"}
    ).json()
    item = world.actor.patch(
        f"{world.base}/items/{world.item['id']}", {"topic_id": other_topic["id"]}
    )
    assert item.json()["topic_id"] == other_topic["id"]


def test_parents_must_exist_inside_the_same_project(world: World) -> None:
    missing = world.actor.post(f"{world.base}/topics", {"module_id": str(uuid4()), "title": "x"})
    assert missing.status_code == 404
    assert missing.json() == {"error": "not_found"}
    assert (
        world.actor.post(
            f"{world.base}/items", world.item_payload(topic_id=str(uuid4()))
        ).status_code
        == 404
    )


def test_cross_project_references_are_rejected_even_for_the_same_owner(world: World) -> None:
    second = world.actor.post(P, {"title": "Second"}).json()
    base2 = f"{P}/{second['id']}"
    # creating under project 2 with project 1's module / topic
    assert (
        world.actor.post(
            f"{base2}/topics", {"module_id": world.module["id"], "title": "x"}
        ).status_code
        == 404
    )
    assert (
        world.actor.post(
            f"{base2}/items", world.item_payload(topic_id=world.topic["id"])
        ).status_code
        == 404
    )
    # moving an item of project 1 into project 2's topic
    module2 = world.actor.post(f"{base2}/modules", {"title": "m"}).json()
    topic2 = world.actor.post(f"{base2}/topics", {"module_id": module2["id"], "title": "t"}).json()
    assert (
        world.actor.patch(
            f"{world.base}/items/{world.item['id']}", {"topic_id": topic2["id"]}
        ).status_code
        == 404
    )
    # reading project 1's item through project 2's path
    assert world.actor.get(f"{base2}/items/{world.item['id']}").status_code == 404


def test_content_endpoints_require_authentication(world: World) -> None:
    world.actor.client.cookies.clear()
    assert world.actor.client.get(f"{world.base}/items").status_code == 401


def test_a_duplicate_prompt_in_the_same_project_conflicts(world: World) -> None:
    again = world.actor.post(
        f"{world.base}/items", world.item_payload(prompt="  tell me ABOUT yourself. ")
    )
    assert again.status_code == 409
    assert again.json() == {"error": "duplicate"}


def test_the_same_prompt_with_another_type_is_allowed(world: World) -> None:
    phrase = world.actor.post(f"{world.base}/items", world.item_payload(type="phrase"))
    assert phrase.status_code == 201


def test_the_same_prompt_is_allowed_in_another_project(world: World) -> None:
    other = world.actor.post(P, {"title": "Other"}).json()
    module = world.actor.post(f"{P}/{other['id']}/modules", {"title": "m"}).json()
    topic = world.actor.post(
        f"{P}/{other['id']}/topics", {"module_id": module["id"], "title": "t"}
    ).json()
    created = world.actor.post(f"{P}/{other['id']}/items", world.item_payload(topic_id=topic["id"]))
    assert created.status_code == 201


def test_updating_a_prompt_into_a_duplicate_conflicts(world: World) -> None:
    second = world.actor.post(f"{world.base}/items", world.item_payload(prompt="Another one?"))
    url = f"{world.base}/items/{second.json()['id']}"
    clash = world.actor.patch(url, {"prompt": "Tell me about yourself."})
    assert clash.status_code == 409
    assert world.actor.get(url).json()["prompt"] == "Another one?"


def test_changing_the_prompt_updates_the_duplicate_identity(world: World) -> None:
    url = f"{world.base}/items/{world.item['id']}"
    world.actor.patch(url, {"prompt": "A brand new prompt?"})
    reuse = world.actor.post(f"{world.base}/items", world.item_payload())
    assert reuse.status_code == 201  # the old prompt is free again


def test_external_id_and_practice_modes_round_trip_and_external_id_is_unique(
    world: World,
) -> None:
    payload = world.item_payload(
        prompt="With ids?", external_id="ext-1", practice_modes=["read_aloud", "fill_gaps"]
    )
    created = world.actor.post(f"{world.base}/items", payload)
    assert created.status_code == 201
    assert created.json()["external_id"] == "ext-1"
    assert created.json()["practice_modes"] == ["read_aloud", "fill_gaps"]
    clash = world.actor.post(
        f"{world.base}/items", world.item_payload(prompt="Other text?", external_id="ext-1")
    )
    assert clash.status_code == 409
    bad = world.actor.post(
        f"{world.base}/items", world.item_payload(prompt="Bad modes?", practice_modes=["teleport"])
    )
    assert bad.status_code == 422
