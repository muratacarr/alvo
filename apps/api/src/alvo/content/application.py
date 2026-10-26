"""Content use cases.

Every operation starts with `require_project`, so ownership is decided in exactly one place
(the projects module). Parents referenced in a request must exist *inside the same project*
and must not be archived.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alvo.content.domain import (
    ApplyResult,
    ContentPlan,
    DedupeIndex,
    ItemRecord,
    ItemType,
    ModuleRecord,
    TopicRecord,
    item_fingerprint,
    loose_key,
)
from alvo.content.infrastructure import SqlContentStore
from alvo.identity.domain import Principal
from alvo.projects.application import require_project
from alvo.shared.errors import ApiError
from alvo.shared.pagination import MAX_PAGE_SIZE, decode_cursor, encode_cursor


def _not_found() -> ApiError:
    return ApiError(404, "not_found")


def _page[R: (ModuleRecord, TopicRecord, ItemRecord)](
    rows: list[R], limit: int
) -> tuple[list[R], str | None]:
    page = rows[:limit]
    more = len(rows) > limit and bool(page)
    return page, encode_cursor(page[-1].created_at, page[-1].id) if more else None


def _list_args(cursor: str | None, limit: int, include_archived: bool) -> dict[str, Any]:
    limit = min(limit, MAX_PAGE_SIZE)
    return {
        "include_archived": include_archived,
        "after": decode_cursor(cursor) if cursor else None,
        "limit": limit + 1,
    }


def _live_module(store: SqlContentStore, project_id: UUID, module_id: UUID) -> ModuleRecord:
    module = store.get_module(project_id, module_id)
    if module is None:
        raise _not_found()
    if module.archived:
        raise ApiError(409, "archived")
    return module


def _live_topic(store: SqlContentStore, project_id: UUID, topic_id: UUID) -> TopicRecord:
    topic = store.get_topic(project_id, topic_id)
    if topic is None:
        raise _not_found()
    if topic.archived:
        raise ApiError(409, "archived")
    return topic


# modules ---------------------------------------------------------------------------------


def create_module(
    db: Session, principal: Principal, project_id: UUID, title: str, now: datetime
) -> ModuleRecord:
    require_project(db, principal, project_id, writable=True)
    module = SqlContentStore(db).create_module(project_id, title, now)
    db.commit()
    return module


def list_modules(
    db: Session,
    principal: Principal,
    project_id: UUID,
    *,
    cursor: str | None,
    limit: int,
    include_archived: bool,
) -> tuple[list[ModuleRecord], str | None]:
    require_project(db, principal, project_id)
    args = _list_args(cursor, limit, include_archived)
    return _page(SqlContentStore(db).list_modules(project_id, **args), min(limit, MAX_PAGE_SIZE))


def get_module(
    db: Session, principal: Principal, project_id: UUID, module_id: UUID
) -> ModuleRecord:
    require_project(db, principal, project_id)
    module = SqlContentStore(db).get_module(project_id, module_id)
    if module is None:
        raise _not_found()
    return module


def update_module(
    db: Session,
    principal: Principal,
    project_id: UUID,
    module_id: UUID,
    changes: dict[str, Any],
    now: datetime,
) -> ModuleRecord:
    require_project(db, principal, project_id, writable=True)
    module = SqlContentStore(db).update_module(project_id, module_id, changes, now)
    if module is None:
        raise _not_found()
    db.commit()
    return module


def archive_module(
    db: Session, principal: Principal, project_id: UUID, module_id: UUID, now: datetime
) -> None:
    require_project(db, principal, project_id, writable=True)
    if not SqlContentStore(db).archive_module(project_id, module_id, now):
        raise _not_found()
    db.commit()


# topics ----------------------------------------------------------------------------------


def create_topic(
    db: Session,
    principal: Principal,
    project_id: UUID,
    module_id: UUID,
    title: str,
    now: datetime,
) -> TopicRecord:
    require_project(db, principal, project_id, writable=True)
    store = SqlContentStore(db)
    _live_module(store, project_id, module_id)
    topic = store.create_topic(project_id, module_id, title, now)
    db.commit()
    return topic


def list_topics(
    db: Session,
    principal: Principal,
    project_id: UUID,
    *,
    module_id: UUID | None,
    cursor: str | None,
    limit: int,
    include_archived: bool,
) -> tuple[list[TopicRecord], str | None]:
    require_project(db, principal, project_id)
    args = _list_args(cursor, limit, include_archived)
    rows = SqlContentStore(db).list_topics(project_id, module_id, **args)
    return _page(rows, min(limit, MAX_PAGE_SIZE))


def get_topic(db: Session, principal: Principal, project_id: UUID, topic_id: UUID) -> TopicRecord:
    require_project(db, principal, project_id)
    topic = SqlContentStore(db).get_topic(project_id, topic_id)
    if topic is None:
        raise _not_found()
    return topic


def update_topic(
    db: Session,
    principal: Principal,
    project_id: UUID,
    topic_id: UUID,
    changes: dict[str, Any],
    now: datetime,
) -> TopicRecord:
    require_project(db, principal, project_id, writable=True)
    store = SqlContentStore(db)
    if "module_id" in changes:
        _live_module(store, project_id, changes["module_id"])
    topic = store.update_topic(project_id, topic_id, changes, now)
    if topic is None:
        raise _not_found()
    db.commit()
    return topic


def archive_topic(
    db: Session, principal: Principal, project_id: UUID, topic_id: UUID, now: datetime
) -> None:
    require_project(db, principal, project_id, writable=True)
    if not SqlContentStore(db).archive_topic(project_id, topic_id, now):
        raise _not_found()
    db.commit()


# items -----------------------------------------------------------------------------------


def create_item(
    db: Session, principal: Principal, project_id: UUID, values: dict[str, Any], now: datetime
) -> ItemRecord:
    require_project(db, principal, project_id, writable=True)
    store = SqlContentStore(db)
    _live_topic(store, project_id, values["topic_id"])
    values = {
        **values,
        "fingerprint": item_fingerprint(ItemType(values["type"]), values["prompt"]),
        "loose_key": loose_key(values["prompt"]),
    }
    try:
        item = store.create_item(project_id, values, now)
        db.commit()
    except IntegrityError as exc:
        # Same type and prompt (or external id) already exists in this project.
        db.rollback()
        raise ApiError(409, "duplicate") from exc
    return item


def list_items(
    db: Session,
    principal: Principal,
    project_id: UUID,
    *,
    topic_id: UUID | None,
    cursor: str | None,
    limit: int,
    include_archived: bool,
) -> tuple[list[ItemRecord], str | None]:
    require_project(db, principal, project_id)
    args = _list_args(cursor, limit, include_archived)
    rows = SqlContentStore(db).list_items(project_id, topic_id, **args)
    return _page(rows, min(limit, MAX_PAGE_SIZE))


def get_item(db: Session, principal: Principal, project_id: UUID, item_id: UUID) -> ItemRecord:
    require_project(db, principal, project_id)
    item = SqlContentStore(db).get_item(project_id, item_id)
    if item is None:
        raise _not_found()
    return item


def update_item(
    db: Session,
    principal: Principal,
    project_id: UUID,
    item_id: UUID,
    changes: dict[str, Any],
    now: datetime,
) -> ItemRecord:
    require_project(db, principal, project_id, writable=True)
    store = SqlContentStore(db)
    if "topic_id" in changes:
        _live_topic(store, project_id, changes["topic_id"])
    current = store.get_item(project_id, item_id)
    if current is None:
        raise _not_found()
    if "prompt" in changes or "type" in changes:
        new_type = ItemType(changes.get("type", current.type))
        new_prompt = changes.get("prompt", current.prompt)
        changes = {
            **changes,
            "fingerprint": item_fingerprint(new_type, new_prompt),
            "loose_key": loose_key(new_prompt),
        }
    try:
        item = store.update_item(project_id, item_id, changes, now)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "duplicate") from exc
    if item is None:
        raise _not_found()
    return item


def archive_item(
    db: Session, principal: Principal, project_id: UUID, item_id: UUID, now: datetime
) -> None:
    require_project(db, principal, project_id, writable=True)
    if not SqlContentStore(db).archive_item(project_id, item_id, now):
        raise _not_found()
    db.commit()


# bulk operations used by the imports module -------------------------------------------------


def load_dedupe_index(db: Session, project_id: UUID) -> DedupeIndex:
    """Read model for duplicate detection. The caller must already have checked ownership."""
    return SqlContentStore(db).load_dedupe_index(project_id)


def apply_content_plan(
    db: Session, project_id: UUID, plan: ContentPlan, now: datetime
) -> ApplyResult:
    """Write a planned import. The caller owns the transaction (commit or roll back)."""
    return SqlContentStore(db).apply_plan(project_id, plan, now)


def export_tree(
    db: Session, project_id: UUID
) -> list[tuple[ModuleRecord, list[tuple[TopicRecord, list[ItemRecord]]]]]:
    """Live content of a project, ready to serialise. Ownership is the caller's job."""
    return SqlContentStore(db).export_tree(project_id)
