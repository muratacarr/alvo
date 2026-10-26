"""Project use cases and the ownership guard other modules call."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from alvo.identity.domain import Principal
from alvo.projects.domain import ProjectRecord
from alvo.projects.infrastructure import SqlProjectStore
from alvo.shared.errors import ApiError
from alvo.shared.pagination import MAX_PAGE_SIZE, decode_cursor, encode_cursor


def require_project(
    db: Session, principal: Principal, project_id: UUID, *, writable: bool = False
) -> ProjectRecord:
    """The one ownership check for project-scoped data.

    A project owned by someone else and a project that does not exist both raise the same
    404, so ids cannot be probed. Writes to an archived project raise 409.
    """
    project = SqlProjectStore(db).get_owned(principal.user_id, project_id)
    if project is None:
        raise ApiError(404, "not_found")
    if writable and project.archived:
        raise ApiError(409, "archived")
    return project


def create_project(
    db: Session, principal: Principal, title: str, description: str | None, now: datetime
) -> ProjectRecord:
    project = SqlProjectStore(db).create(principal.user_id, title, description, now)
    db.commit()
    return project


def list_projects(
    db: Session,
    principal: Principal,
    *,
    include_archived: bool,
    cursor: str | None,
    limit: int,
) -> tuple[list[ProjectRecord], str | None]:
    limit = min(limit, MAX_PAGE_SIZE)
    after = decode_cursor(cursor) if cursor else None
    rows = SqlProjectStore(db).list_owned(
        principal.user_id, include_archived=include_archived, after=after, limit=limit + 1
    )
    page = rows[:limit]
    next_cursor = (
        encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit and page else None
    )
    return page, next_cursor


def update_project(
    db: Session,
    principal: Principal,
    project_id: UUID,
    changes: dict[str, Any],
    now: datetime,
) -> ProjectRecord:
    require_project(db, principal, project_id, writable=True)
    project = SqlProjectStore(db).update(principal.user_id, project_id, changes, now)
    db.commit()
    if project is None:
        raise ApiError(404, "not_found")
    return project


def archive_project(db: Session, principal: Principal, project_id: UUID, now: datetime) -> None:
    require_project(db, principal, project_id)
    SqlProjectStore(db).set_archived(principal.user_id, project_id, now, now)
    db.commit()


def unarchive_project(
    db: Session, principal: Principal, project_id: UUID, now: datetime
) -> ProjectRecord:
    require_project(db, principal, project_id)
    project = SqlProjectStore(db).set_archived(principal.user_id, project_id, None, now)
    db.commit()
    if project is None:
        raise ApiError(404, "not_found")
    return project
