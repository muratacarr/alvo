"""HTTP transport for projects. The owner always comes from the session, never the body."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy.orm import Session

from alvo.identity.api import csrf_principal_dependency, get_db, principal_dependency, verify_origin
from alvo.identity.domain import Principal
from alvo.projects import application
from alvo.projects.domain import ProjectRecord
from alvo.shared.http import get_now
from alvo.shared.pagination import Page, PageLimit
from alvo.shared.schemas import PatchModel
from alvo.shared.text import CLEAN

Title = Annotated[str, CLEAN, StringConstraints(min_length=1, max_length=200)]
Description = Annotated[str, CLEAN, StringConstraints(min_length=1, max_length=2000)]


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: Title
    description: Description | None = None


class ProjectUpdate(PatchModel):
    not_nullable = ("title",)
    title: Title | None = None
    description: Description | None = None


class ProjectOut(BaseModel):
    id: UUID
    title: str
    description: str | None
    archived: bool
    created_at: datetime
    updated_at: datetime


def to_out(project: ProjectRecord) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        title=project.title,
        description=project.description,
        archived=project.archived,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


router = APIRouter(prefix="/api/v1/projects", dependencies=[Depends(verify_origin)])

Reader = Annotated[Principal, Depends(principal_dependency)]
Writer = Annotated[Principal, Depends(csrf_principal_dependency)]
Db = Annotated[Session, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]


@router.post("", status_code=201)
def create_project(body: ProjectCreate, principal: Writer, db: Db, now: Now) -> ProjectOut:
    return to_out(application.create_project(db, principal, body.title, body.description, now))


@router.get("")
def list_projects(
    principal: Reader,
    db: Db,
    limit: PageLimit = 50,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    include_archived: bool = False,
) -> Page[ProjectOut]:
    projects, next_cursor = application.list_projects(
        db, principal, include_archived=include_archived, cursor=cursor, limit=limit
    )
    return Page[ProjectOut](items=[to_out(p) for p in projects], next_cursor=next_cursor)


@router.get("/{project_id}")
def get_project(project_id: UUID, principal: Reader, db: Db) -> ProjectOut:
    return to_out(application.require_project(db, principal, project_id))


@router.patch("/{project_id}")
def update_project(
    project_id: UUID, body: ProjectUpdate, principal: Writer, db: Db, now: Now
) -> ProjectOut:
    changes = body.changes()
    return to_out(application.update_project(db, principal, project_id, changes, now))


@router.delete("/{project_id}", status_code=204)
def archive_project(project_id: UUID, principal: Writer, db: Db, now: Now) -> Response:
    application.archive_project(db, principal, project_id, now)
    return Response(status_code=204)


@router.post("/{project_id}/unarchive")
def unarchive_project(project_id: UUID, principal: Writer, db: Db, now: Now) -> ProjectOut:
    return to_out(application.unarchive_project(db, principal, project_id, now))
