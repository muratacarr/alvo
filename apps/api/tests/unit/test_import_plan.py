"""Planning is pure: given a parsed document and what already exists, decide what to add."""

import json
from typing import Any
from uuid import uuid4

from alvo.content.domain import DedupeIndex, ItemType, item_fingerprint, loose_key, title_key
from alvo.imports.domain import plan_import
from alvo.imports.parsing import parse_document


def parsed(items: list[dict[str, Any]], module: str = "M", topic: str = "T") -> Any:
    body = {
        "schemaVersion": "1.0",
        "program": {
            "title": "P",
            "modules": [{"title": module, "topics": [{"title": topic, "items": items}]}],
        },
    }
    return parse_document(json.dumps(body).encode())


def q(prompt: str, **extra: Any) -> dict[str, Any]:
    return {"type": "question", "prompt": prompt, **extra}


def empty_index() -> DedupeIndex:
    return DedupeIndex(set(), set(), {}, {}, {})


def planned_prompts(plan: Any) -> list[str]:
    return [i.fields.prompt for m in plan.content.modules for t in m.topics for i in t.items]


def test_everything_is_new_in_an_empty_project() -> None:
    plan = plan_import(parsed([q("A?"), q("B?")]), empty_index(), "skip")
    assert planned_prompts(plan) == ["A?", "B?"]
    c = plan.counts
    assert (c.new_items, c.new_modules, c.new_topics) == (2, 1, 1)
    assert c.duplicate_content == c.duplicate_external_id == c.ambiguous == 0


def test_exact_duplicates_are_skipped_and_counted() -> None:
    index = empty_index()
    index.fingerprints.add(item_fingerprint(ItemType.QUESTION, "What is DI?"))
    plan = plan_import(parsed([q("what  is DI?"), q("New one?")]), index, "skip")
    assert planned_prompts(plan) == ["New one?"]
    assert plan.counts.duplicate_content == 1


def test_existing_external_id_wins_even_when_content_differs() -> None:
    index = empty_index()
    index.external_ids.add("ext-1")
    plan = plan_import(parsed([q("Completely different text", externalId="ext-1")]), index, "skip")
    assert planned_prompts(plan) == []
    assert plan.counts.duplicate_external_id == 1


def test_repeats_inside_the_file_keep_only_the_first() -> None:
    plan = plan_import(parsed([q("Same?"), q("same?"), q("Other?")]), empty_index(), "skip")
    assert planned_prompts(plan) == ["Same?", "Other?"]
    assert plan.counts.duplicate_in_file == 1


def test_repeated_external_ids_inside_the_file_keep_only_the_first() -> None:
    items = [q("One?", externalId="x"), q("Two?", externalId="x")]
    plan = plan_import(parsed(items), empty_index(), "skip")
    assert planned_prompts(plan) == ["One?"]
    assert plan.counts.duplicate_in_file == 1


def test_near_duplicates_are_flagged_and_skipped_by_default() -> None:
    index = empty_index()
    index.fingerprints.add(item_fingerprint(ItemType.QUESTION, "What's your name?"))
    index.loose_keys[("question", loose_key("What's your name?"))] = "What's your name?"
    plan = plan_import(parsed([q("Whats your name")]), index, "skip")
    assert planned_prompts(plan) == []
    assert plan.counts.ambiguous == 1
    assert plan.ambiguous[0].existing_prompt == "What's your name?"


def test_near_duplicates_can_be_added_explicitly() -> None:
    index = empty_index()
    index.fingerprints.add(item_fingerprint(ItemType.QUESTION, "What's your name?"))
    index.loose_keys[("question", loose_key("What's your name?"))] = "What's your name?"
    plan = plan_import(parsed([q("Whats your name")]), index, "add")
    assert planned_prompts(plan) == ["Whats your name"]
    assert plan.counts.new_items == 1 and plan.counts.ambiguous == 1


def test_existing_modules_and_topics_are_reused_by_title() -> None:
    module_id, topic_id = uuid4(), uuid4()
    index = empty_index()
    index.modules[title_key("technical interview")] = module_id
    index.topics[(module_id, title_key("di"))] = topic_id
    plan = plan_import(parsed([q("A?")], module="Technical  Interview", topic="DI"), index, "skip")
    module = plan.content.modules[0]
    assert module.existing_id == module_id
    assert module.topics[0].existing_id == topic_id
    assert (plan.counts.new_modules, plan.counts.new_topics) == (0, 0)


def test_containers_without_new_items_are_not_created() -> None:
    index = empty_index()
    index.fingerprints.add(item_fingerprint(ItemType.QUESTION, "A?"))
    plan = plan_import(parsed([q("A?")]), index, "skip")
    assert plan.content.modules == []
    assert (plan.counts.new_modules, plan.counts.new_topics) == (0, 0)


def test_duplicate_titles_in_the_file_share_one_container() -> None:
    body = {
        "schemaVersion": "1.0",
        "program": {
            "title": "P",
            "modules": [
                {"title": "M", "topics": [{"title": "T", "items": [q("A?")]}]},
                {"title": "m", "topics": [{"title": "t", "items": [q("B?")]}]},
            ],
        },
    }
    plan = plan_import(parse_document(json.dumps(body).encode()), empty_index(), "skip")
    assert len(plan.content.modules) == 1
    assert len(plan.content.modules[0].topics) == 1
    assert planned_prompts(plan) == ["A?", "B?"]


def test_invalid_entries_are_counted_but_never_planned() -> None:
    plan = plan_import(parsed([q("A?"), {"type": "nope", "prompt": "x"}]), empty_index(), "skip")
    assert plan.counts.invalid == 1
    assert planned_prompts(plan) == ["A?"]


def test_samples_are_bounded() -> None:
    plan = plan_import(parsed([q(f"Q{i}?") for i in range(40)]), empty_index(), "skip")
    assert len(plan.new_samples) <= 10
