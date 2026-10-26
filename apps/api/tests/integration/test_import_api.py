"""Import preview/commit/export against a real PostgreSQL."""

import json
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from alvo.imports.parsing import load_schema
from tests.integration.support import Actor

P = "/api/v1/projects"
NewActor = Callable[..., Actor]


def q(prompt: str, **extra: Any) -> dict[str, Any]:
    return {"type": "question", "prompt": prompt, **extra}


def make_doc(
    items: list[Any], module: str = "Technical Interview", topic: str = "Dependency Injection"
) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "program": {
            "title": "Backend Developer Interview",
            "targetLanguage": "en",
            "modules": [{"title": module, "topics": [{"title": topic, "items": items}]}],
        },
    }


def body(document: Any) -> bytes:
    return json.dumps(document).encode()


def new_project(actor: Actor, title: str = "Target") -> str:
    response = actor.post(P, {"title": title})
    assert response.status_code == 201
    return str(response.json()["id"])


def preview(actor: Actor, pid: str, document: Any) -> Any:
    return actor.post_raw(f"{P}/{pid}/imports/preview", body(document))


def commit(
    actor: Actor, pid: str, document: Any, key: str | None = None, mode: str = "skip"
) -> Any:
    return actor.post_raw(
        f"{P}/{pid}/imports/commit?ambiguous={mode}",
        body(document),
        {"Idempotency-Key": key or uuid4().hex},
    )


def all_items(actor: Actor, pid: str, include_archived: bool = True) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor = None
    while True:
        url = f"{P}/{pid}/items?limit=100&include_archived={str(include_archived).lower()}"
        page = actor.get(url + (f"&cursor={cursor}" if cursor else "")).json()
        items += page["items"]
        cursor = page["next_cursor"]
        if cursor is None:
            return items


def count(actor: Actor, pid: str, kind: str) -> int:
    return len(actor.get(f"{P}/{pid}/{kind}?limit=100&include_archived=true").json()["items"])


# preview ---------------------------------------------------------------------------------


def test_preview_reports_counts_and_writes_nothing(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    response = preview(actor, pid, make_doc([q("A?"), q("B?")]))
    assert response.status_code == 200
    result = response.json()
    assert result["program_title"] == "Backend Developer Interview"
    assert result["counts"]["new_items"] == 2
    assert (result["counts"]["new_modules"], result["counts"]["new_topics"]) == (1, 1)
    assert [s["prompt"] for s in result["new_samples"]] == ["A?", "B?"]
    assert all_items(actor, pid) == []
    assert count(actor, pid, "modules") == 0 and count(actor, pid, "topics") == 0


def test_preview_lists_invalid_entries_without_echoing_values(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    document = make_doc([q("ok"), {"type": "question", "prompt": "x", "id": "SecretValue99"}])
    result = preview(actor, pid, document).json()
    assert result["counts"]["invalid"] == 1
    assert result["invalid"][0]["path"] == "modules[0].topics[0].items[1]"
    assert "SecretValue99" not in json.dumps(result)


# commit ----------------------------------------------------------------------------------


def test_commit_creates_the_hierarchy_and_items(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    document = make_doc(
        [q("What is DI?", externalId="di-1", sampleAnswer="Reduces coupling.", keywords=["k"])]
    )
    response = commit(actor, pid, document)
    assert response.status_code == 200
    result = response.json()
    assert result["replayed"] is False
    assert result["counts"]["new_items"] == 1
    items = all_items(actor, pid)
    assert items[0]["external_id"] == "di-1"
    assert items[0]["sample_answer"] == "Reduces coupling."
    modules = actor.get(f"{P}/{pid}/modules").json()["items"]
    assert [m["title"] for m in modules] == ["Technical Interview"]
    topics = actor.get(f"{P}/{pid}/topics").json()["items"]
    assert [t["title"] for t in topics] == ["Dependency Injection"]
    assert topics[0]["module_id"] == modules[0]["id"]


def test_reimporting_the_same_file_adds_nothing(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    document = make_doc([q("A?", externalId="a"), q("B?")])
    commit(actor, pid, document)
    second = commit(actor, pid, document).json()
    assert second["counts"]["new_items"] == 0
    assert second["counts"]["new_modules"] == second["counts"]["new_topics"] == 0
    assert len(all_items(actor, pid)) == 2
    assert count(actor, pid, "modules") == 1 and count(actor, pid, "topics") == 1


def test_overlapping_file_adds_only_new_items_and_keeps_customised_answers(
    new_actor: NewActor,
) -> None:
    actor = new_actor()
    pid = new_project(actor)
    commit(actor, pid, make_doc([q("What is DI?", sampleAnswer="Original answer.")]))
    mine = all_items(actor, pid)[0]
    actor.patch(f"{P}/{pid}/items/{mine['id']}", {"sample_answer": "My own words."})
    overlap = make_doc([q("What is DI?", sampleAnswer="AI generated answer."), q("What is IoC?")])
    result = commit(actor, pid, overlap).json()
    assert result["counts"]["new_items"] == 1
    assert result["counts"]["duplicate_content"] == 1
    kept = actor.get(f"{P}/{pid}/items/{mine['id']}").json()
    assert kept["sample_answer"] == "My own words."
    assert sorted(i["prompt"] for i in all_items(actor, pid)) == ["What is DI?", "What is IoC?"]


def test_existing_external_id_is_never_overwritten(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    commit(actor, pid, make_doc([q("Original?", externalId="x1")]))
    result = commit(actor, pid, make_doc([q("Rewritten entirely", externalId="x1")])).json()
    assert result["counts"]["duplicate_external_id"] == 1
    assert [i["prompt"] for i in all_items(actor, pid)] == ["Original?"]


def test_archived_items_are_not_resurrected(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    commit(actor, pid, make_doc([q("Old question?")]))
    item = all_items(actor, pid)[0]
    actor.delete(f"{P}/{pid}/items/{item['id']}")
    result = commit(actor, pid, make_doc([q("Old question?")])).json()
    assert result["counts"]["new_items"] == 0
    assert result["counts"]["duplicate_content"] == 1
    assert all_items(actor, pid, include_archived=False) == []


def test_near_duplicates_are_flagged_and_skipped_unless_added(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    commit(actor, pid, make_doc([q("What's your name?")]))
    near = make_doc([q("Whats your name")])
    shown = preview(actor, pid, near).json()
    assert shown["counts"]["ambiguous"] == 1
    assert shown["ambiguous"][0]["existing_prompt"] == "What's your name?"
    assert commit(actor, pid, near).json()["counts"]["new_items"] == 0
    assert len(all_items(actor, pid)) == 1
    added = commit(actor, pid, near, mode="add").json()
    assert added["counts"]["new_items"] == 1
    assert len(all_items(actor, pid)) == 2


def test_commit_with_invalid_entries_is_refused_and_writes_nothing(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    document = make_doc([q("fine"), {"type": "question", "prompt": "bad", "id": "1"}])
    response = commit(actor, pid, document)
    assert response.status_code == 422
    assert response.json() == {"error": "invalid_items", "count": 1}
    assert all_items(actor, pid) == [] and count(actor, pid, "modules") == 0


def test_commit_is_atomic_when_the_database_rejects_midway(
    new_actor: NewActor, migrated_database_url: str
) -> None:
    actor = new_actor()
    pid = new_project(actor)
    engine = create_engine(migrated_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE learning_items ADD CONSTRAINT zz_fail CHECK (prompt <> 'BOOM')")
            )
        try:
            # The failure surfaces as a server error (TestClient re-raises it); what matters
            # is that the half-applied import left nothing behind.
            with pytest.raises(IntegrityError):
                commit(actor, pid, make_doc([q("first"), q("BOOM"), q("third")]))
        finally:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE learning_items DROP CONSTRAINT zz_fail"))
    finally:
        engine.dispose()
    assert all_items(actor, pid) == []
    assert count(actor, pid, "modules") == 0


def test_idempotency_key_replays_the_stored_result(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    document = make_doc([q("A?"), q("B?")])
    first = commit(actor, pid, document, key="key-1").json()
    again = commit(actor, pid, document, key="key-1").json()
    assert again["replayed"] is True
    assert again["job_id"] == first["job_id"]
    assert again["counts"] == first["counts"]
    assert len(all_items(actor, pid)) == 2


def test_reusing_a_key_for_a_different_document_conflicts(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    commit(actor, pid, make_doc([q("A?")]), key="key-2")
    other = commit(actor, pid, make_doc([q("Different?")]), key="key-2")
    assert other.status_code == 409
    assert other.json() == {"error": "idempotency_key_reuse"}
    assert len(all_items(actor, pid)) == 1


def test_reformatted_documents_share_one_digest_for_replay(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    document = make_doc([q("A?")])
    commit(actor, pid, document, key="key-3")
    pretty = actor.post_raw(
        f"{P}/{pid}/imports/commit",
        json.dumps(document, indent=4).encode(),
        {"Idempotency-Key": "key-3"},
    )
    assert pretty.status_code == 200 and pretty.json()["replayed"] is True


@pytest.mark.parametrize("key", ["", "x" * 65, "bad key", "a/b"])
def test_idempotency_key_is_required_and_validated(new_actor: NewActor, key: str) -> None:
    actor = new_actor()
    pid = new_project(actor)
    headers = {"Idempotency-Key": key} if key else {}
    response = actor.post_raw(f"{P}/{pid}/imports/commit", body(make_doc([q("A?")])), headers)
    assert response.status_code == 422


def test_concurrent_imports_never_create_duplicates(new_actor: NewActor) -> None:
    subject = uuid4().hex
    first, second = new_actor(subject), new_actor(subject)
    pid = new_project(first)
    document = make_doc([q(f"Question {n}?") for n in range(40)])
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(commit, who, pid, document) for who in (first, second)]
        results = [f.result() for f in futures]
    assert all(r.status_code == 200 for r in results)
    assert sorted(r.json()["counts"]["new_items"] for r in results) == [0, 40]
    assert len(all_items(first, pid)) == 40
    assert count(first, pid, "modules") == 1 and count(first, pid, "topics") == 1


def test_concurrent_requests_with_the_same_key_run_once(new_actor: NewActor) -> None:
    subject = uuid4().hex
    first, second = new_actor(subject), new_actor(subject)
    pid = new_project(first)
    document = make_doc([q(f"Question {n}?") for n in range(25)])
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(commit, who, pid, document, "same-key") for who in (first, second)]
        results = [f.result().json() for f in futures]
    assert sorted(r["replayed"] for r in results) == [False, True]
    assert len(all_items(first, pid)) == 25


def test_import_jobs_record_metadata_but_never_the_content(
    new_actor: NewActor, migrated_database_url: str
) -> None:
    actor = new_actor()
    pid = new_project(actor)
    commit(actor, pid, make_doc([q("Highly private interview answer")]), key="audit-1")
    engine = create_engine(migrated_database_url)
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT * FROM import_jobs WHERE idempotency_key = 'audit-1'")
        ).one()
    engine.dispose()
    assert str(row.owner_id) == actor.user_id
    assert row.status == "committed" and len(row.source_digest) == 64
    assert "Highly private" not in json.dumps([str(v) for v in row])


def test_commits_are_rate_limited_per_user(new_actor: NewActor) -> None:
    actor = new_actor(import_commits_per_hour="2")
    pid = new_project(actor)
    for n in range(2):
        assert commit(actor, pid, make_doc([q(f"Q{n}?")])).status_code == 200
    limited = commit(actor, pid, make_doc([q("Q3?")]))
    assert limited.status_code == 429
    assert limited.json() == {"error": "rate_limited"}


# limits and hostile input -----------------------------------------------------------------


def test_oversized_imports_are_rejected(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    huge = make_doc([q("x", sampleAnswer="d" * 9000) for _ in range(300)])
    assert len(body(huge)) > 2 * 1024 * 1024
    assert preview(actor, pid, huge).status_code == 413


def test_import_larger_than_the_normal_request_limit_is_accepted_up_to_its_own_cap(
    new_actor: NewActor,
) -> None:
    actor = new_actor()
    pid = new_project(actor)
    big = make_doc([q(f"Q{n}?", sampleAnswer="d" * 5000) for n in range(300)])
    assert 1024 * 1024 < len(body(big)) < 2 * 1024 * 1024
    assert preview(actor, pid, big).status_code == 200


def test_too_many_items_is_rejected(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    response = preview(actor, pid, make_doc([q(f"Q{n}") for n in range(2001)]))
    assert response.status_code == 422
    assert response.json()["error"] == "too_many_items"


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"{broken", "invalid_json"),
        (b'{"schemaVersion":"1.0","schemaVersion":"1.0"}', "duplicate_key"),
        (b'{"schemaVersion":"9.9","program":{}}', "unsupported_schema_version"),
        pytest.param(b"[" * 50_000 + b"]" * 50_000, "invalid_json", id="deep-nesting"),
    ],
)
def test_malformed_documents_get_a_stable_error_code(
    new_actor: NewActor, payload: bytes, code: str
) -> None:
    actor = new_actor()
    pid = new_project(actor)
    response = actor.post_raw(f"{P}/{pid}/imports/preview", payload)
    assert response.status_code == 422
    assert response.json()["error"] in {code, "too_deep"}


def test_imports_into_an_archived_project_are_refused(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    actor.delete(f"{P}/{pid}")
    assert commit(actor, pid, make_doc([q("A?")])).status_code == 409


def test_import_endpoints_require_csrf(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = new_project(actor)
    response = actor.client.post(
        f"{P}/{pid}/imports/commit",
        content=body(make_doc([q("A?")])),
        headers={
            "Origin": "https://testserver",
            "Content-Type": "application/json",
            "Idempotency-Key": "k",
        },
    )
    assert response.status_code == 403


# ownership --------------------------------------------------------------------------------


def test_other_users_cannot_preview_commit_or_export(new_actor: NewActor) -> None:
    owner, intruder = new_actor(), new_actor()
    pid = new_project(owner)
    commit(owner, pid, make_doc([q("Private question?")]))
    document = make_doc([q("hijack")])
    assert preview(intruder, pid, document).status_code == 404
    assert commit(intruder, pid, document).status_code == 404
    assert intruder.get(f"{P}/{pid}/export").status_code == 404
    assert [i["prompt"] for i in all_items(owner, pid)] == ["Private question?"]


def test_deduplication_never_looks_at_other_users_projects(new_actor: NewActor) -> None:
    alice, bob = new_actor(), new_actor()
    commit(alice, new_project(alice), make_doc([q("Shared text?", externalId="same-id")]))
    bob_project = new_project(bob)
    result = commit(bob, bob_project, make_doc([q("Shared text?", externalId="same-id")])).json()
    assert result["counts"]["new_items"] == 1
    assert result["counts"]["duplicate_content"] == result["counts"]["duplicate_external_id"] == 0


def test_the_same_content_can_exist_in_two_projects_of_one_user(new_actor: NewActor) -> None:
    actor = new_actor()
    first, second = new_project(actor, "One"), new_project(actor, "Two")
    document = make_doc([q("Same?", externalId="s1")])
    assert commit(actor, first, document).json()["counts"]["new_items"] == 1
    assert commit(actor, second, document).json()["counts"]["new_items"] == 1


# export -----------------------------------------------------------------------------------

UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def seeded_project(actor: Actor) -> str:
    pid = new_project(actor, "Exported project")
    commit(
        actor,
        pid,
        make_doc(
            [
                q("What is DI?", externalId="di-1", sampleAnswer="Coupling.", tags=["backend"]),
                {"type": "phrase", "prompt": "break the ice", "translation": "buzları eritmek"},
            ]
        ),
    )
    return pid


def test_export_is_valid_deterministic_and_content_only(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = seeded_project(actor)
    first, second = actor.get(f"{P}/{pid}/export"), actor.get(f"{P}/{pid}/export")
    assert first.status_code == 200
    assert first.text == second.text
    Draft202012Validator(load_schema()).validate(first.json())
    assert first.json()["program"]["title"] == "Exported project"
    assert not UUID_PATTERN.search(first.text)
    for forbidden in ("owner", "user", "session", "token", "email", "archived", "created"):
        assert forbidden not in first.text.lower()


def test_export_response_headers(new_actor: NewActor) -> None:
    actor = new_actor()
    response = actor.get(f"{P}/{seeded_project(actor)}/export")
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["content-disposition"] == 'attachment; filename="alvo-export.json"'
    assert response.headers["cache-control"] == "no-store"


def test_export_skips_archived_content(new_actor: NewActor) -> None:
    actor = new_actor()
    pid = seeded_project(actor)
    victim = next(i for i in all_items(actor, pid) if i["prompt"] == "break the ice")
    actor.delete(f"{P}/{pid}/items/{victim['id']}")
    prompts = [
        i["prompt"]
        for m in actor.get(f"{P}/{pid}/export").json()["program"]["modules"]
        for t in m["topics"]
        for i in t["items"]
    ]
    assert prompts == ["What is DI?"]


def test_exported_file_round_trips_into_a_new_project(new_actor: NewActor) -> None:
    actor = new_actor()
    source = seeded_project(actor)
    exported = actor.get(f"{P}/{source}/export").json()
    target = new_project(actor, "Copy")
    result = commit(actor, target, exported).json()
    assert result["counts"]["new_items"] == 2
    assert result["counts"]["ambiguous"] == result["counts"]["invalid"] == 0
    again = commit(actor, source, exported).json()
    assert again["counts"]["new_items"] == 0


# templates --------------------------------------------------------------------------------


def test_schema_and_sample_are_downloadable_and_consistent(new_actor: NewActor) -> None:
    actor = new_actor()
    schema = actor.get("/api/v1/templates/import/v1/schema")
    sample = actor.get("/api/v1/templates/import/v1/sample")
    assert schema.status_code == sample.status_code == 200
    Draft202012Validator(schema.json()).validate(sample.json())
    pid = new_project(actor)
    assert preview(actor, pid, sample.json()).json()["counts"]["invalid"] == 0
