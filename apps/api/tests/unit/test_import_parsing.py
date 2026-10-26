import json
from typing import Any

import pytest

from alvo.imports.parsing import (
    MAX_ITEMS,
    ImportRejected,
    load_sample_document,
    parse_document,
)


def doc(items: list[dict[str, Any]] | None = None, **top: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schemaVersion": "1.0",
        "program": {
            "title": "Backend Developer Interview",
            "targetLanguage": "en",
            "level": "B1",
            "modules": [
                {
                    "title": "Technical Interview",
                    "topics": [
                        {
                            "title": "Dependency Injection",
                            "items": items
                            if items is not None
                            else [{"type": "question", "prompt": "What is DI?"}],
                        }
                    ],
                }
            ],
        },
    }
    body.update(top)
    return body


def raw(value: Any) -> bytes:
    return json.dumps(value).encode()


def rejected(payload: bytes) -> ImportRejected:
    with pytest.raises(ImportRejected) as excinfo:
        parse_document(payload)
    return excinfo.value


def test_the_published_sample_parses_without_invalid_entries() -> None:
    parsed = parse_document(json.dumps(load_sample_document()).encode())
    assert parsed.invalid == []
    assert parsed.program_title
    assert sum(len(t.items) for m in parsed.modules for t in m.topics) >= 1


def test_a_minimal_document_parses_and_applies_defaults() -> None:
    parsed = parse_document(raw(doc()))
    item = parsed.modules[0].topics[0].items[0].fields
    assert (item.type.value, item.prompt) == ("question", "What is DI?")
    assert item.keywords == [] and item.external_id is None and item.difficulty is None


def test_all_item_fields_are_mapped_from_camel_case() -> None:
    full = {
        "externalId": "backend-di-001",
        "type": "question",
        "prompt": "What is dependency injection?",
        "sampleAnswer": "It reduces coupling.",
        "translation": "Bağımlılık enjeksiyonu nedir?",
        "keywords": ["coupling"],
        "tags": ["backend"],
        "followUpQuestions": ["How does it help testing?"],
        "difficulty": 3,
        "practice": {"modes": ["read_aloud", "fill_gaps"]},
    }
    item = parse_document(raw(doc([full]))).modules[0].topics[0].items[0].fields
    assert item.external_id == "backend-di-001"
    assert item.sample_answer == "It reduces coupling."
    assert item.follow_up_questions == ["How does it help testing?"]
    assert item.practice_modes == ["read_aloud", "fill_gaps"]
    assert item.difficulty == 3


def test_unparseable_input_is_rejected_with_stable_codes() -> None:
    assert rejected(b"{not json").code == "invalid_json"
    assert rejected(b"\xff\xfe\x00").code == "invalid_json"
    assert rejected(b"[]").code == "invalid_document"
    assert rejected(b'"text"').code == "invalid_document"


def test_nan_and_infinity_are_not_json() -> None:
    assert rejected(b'{"schemaVersion": NaN}').code == "invalid_json"


def test_duplicate_json_keys_are_rejected() -> None:
    payload = b'{"schemaVersion":"1.0","schemaVersion":"1.0","program":{}}'
    assert rejected(payload).code == "duplicate_key"


def test_pathological_nesting_is_rejected_without_crashing() -> None:
    assert rejected(b"[" * 100_000 + b"]" * 100_000).code in {"invalid_json", "too_deep"}


def test_schema_version_is_required_and_must_be_supported() -> None:
    missing = doc()
    del missing["schemaVersion"]
    assert rejected(raw(missing)).code == "schema_version_missing"
    unsupported = rejected(raw(doc(schemaVersion="2.0")))
    assert unsupported.code == "unsupported_schema_version"
    assert unsupported.details["supported"] == ["1.0"]
    assert rejected(raw(doc(schemaVersion=1.0))).code == "unsupported_schema_version"


def test_unknown_top_level_and_program_fields_are_rejected() -> None:
    assert rejected(raw(doc(userId="x"))).code == "invalid_document"
    bad = doc()
    bad["program"]["ownerId"] = "x"
    assert rejected(raw(bad)).code == "invalid_document"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["program"].pop("title"),
        lambda d: d["program"].__setitem__("modules", {}),
        lambda d: d["program"]["modules"][0].pop("topics"),
        lambda d: d["program"]["modules"][0]["topics"][0].pop("items"),
        lambda d: d["program"].__setitem__("title", ""),
        lambda d: d["program"]["modules"][0].__setitem__("title", "x" * 201),
    ],
)
def test_structural_problems_reject_the_whole_document(mutate: Any) -> None:
    body = doc()
    mutate(body)
    assert rejected(raw(body)).code == "invalid_document"


@pytest.mark.parametrize(
    "item",
    [
        {"type": "essay", "prompt": "x"},
        {"type": "question"},
        {"type": "question", "prompt": ""},
        {"type": "question", "prompt": "a\x00b"},
        {"type": "question", "prompt": "x" * 2001},
        {"type": "question", "prompt": "x", "id": "123"},
        {"type": "question", "prompt": "x", "userId": "u"},
        {"type": "question", "prompt": "x", "reviewState": {"stability": 3}},
        {"type": "question", "prompt": "x", "keywords": ["k"] * 31},
        {"type": "question", "prompt": "x", "difficulty": 9},
        {"type": "question", "prompt": "x", "difficulty": "3"},
        {"type": "question", "prompt": "x", "externalId": "has space"},
        {"type": "question", "prompt": "x", "practice": {"modes": ["teleport"]}},
        {"type": "question", "prompt": "x", "practice": {"modes": [], "extra": 1}},
        "not an object",
    ],
)
def test_invalid_items_are_listed_with_their_path_and_do_not_abort_the_parse(
    item: Any,
) -> None:
    parsed = parse_document(raw(doc([{"type": "question", "prompt": "good"}, item])))
    assert len(parsed.modules[0].topics[0].items) == 1
    assert [e.path for e in parsed.invalid] == ["modules[0].topics[0].items[1]"]
    assert parsed.invalid[0].reasons


def test_invalid_entries_never_contain_submitted_values() -> None:
    parsed = parse_document(raw(doc([{"type": "question", "prompt": "x", "id": "SecretValue99"}])))
    assert "SecretValue99" not in repr(parsed.invalid)


def test_item_limit_is_enforced() -> None:
    items = [{"type": "question", "prompt": f"q{i}"} for i in range(MAX_ITEMS + 1)]
    error = rejected(raw(doc(items)))
    assert error.code == "too_many_items"


def test_module_and_topic_limits_are_enforced() -> None:
    body = doc()
    body["program"]["modules"] = [{"title": f"m{i}", "topics": []} for i in range(101)]
    assert rejected(raw(body)).code == "too_many_modules"
    body = doc()
    body["program"]["modules"][0]["topics"] = [{"title": f"t{i}", "items": []} for i in range(201)]
    assert rejected(raw(body)).code == "too_many_topics"


def test_digest_ignores_formatting_but_not_content() -> None:
    compact = parse_document(json.dumps(doc(), separators=(",", ":")).encode()).digest
    pretty = parse_document(json.dumps(doc(), indent=4).encode()).digest
    other = parse_document(raw(doc([{"type": "question", "prompt": "Different"}]))).digest
    assert compact == pretty
    assert compact != other
    assert len(compact) == 64
