"""HTTP transport for modules, topics and learning items, all scoped under a project."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from alvo.content import application
from alvo.content.domain import ItemRecord, ItemType, ModuleRecord, TopicRecord
from alvo.identity.api import csrf_principal_dependency, get_db, principal_dependency, verify_origin
from alvo.identity.domain import Principal
from alvo.shared.http import get_now
from alvo.shared.pagination import Page, PageLimit
from alvo.shared.schemas import PatchModel
from alvo.shared.text import CLEAN

Title = Annotated[str, CLEAN, StringConstraints(min_length=1, max_length=200)]
Prompt = Annotated[str, CLEAN, StringConstraints(min_length=1, max_length=2000)]
Translation = Annotated[str, CLEAN, StringConstraints(min_length=1, max_length=2000)]
SampleAnswer = Annotated[str, CLEAN, StringConstraints(min_length=1, max_length=10000)]
Label = Annotated[str, CLEAN, StringConstraints(min_length=1, max_length=64)]
Question = Annotated[str, CLEAN, StringConstraints(min_length=1, max_length=500)]
Keywords = Annotated[list[Label], Field(max_length=30)]
Tags = Annotated[list[Label], Field(max_length=30)]
FollowUps = Annotated[list[Question], Field(max_length=10)]
Difficulty = Annotated[int, Field(strict=True, ge=1, le=5)]


# request bodies ---------------------------------------------------------------------------


class ModuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title


class ModuleUpdate(PatchModel):
    not_nullable = ("title",)
    title: Title | None = None


class TopicCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    module_id: UUID
    title: Title


class TopicUpdate(PatchModel):
    not_nullable = ("title", "module_id")
    title: Title | None = None
    module_id: UUID | None = None


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: UUID
    type: ItemType
    prompt: Prompt
    sample_answer: SampleAnswer | None = None
    translation: Translation | None = None
    keywords: Keywords = Field(default_factory=list)
    tags: Tags = Field(default_factory=list)
    follow_up_questions: FollowUps = Field(default_factory=list)
    difficulty: Difficulty | None = None


class ItemUpdate(PatchModel):
    not_nullable = ("topic_id", "type", "prompt", "keywords", "tags", "follow_up_questions")
    topic_id: UUID | None = None
    type: ItemType | None = None
    prompt: Prompt | None = None
    sample_answer: SampleAnswer | None = None
    translation: Translation | None = None
    keywords: Keywords | None = None
    tags: Tags | None = None
    follow_up_questions: FollowUps | None = None
    difficulty: Difficulty | None = None


# responses ---------------------------------------------------------------------------------


class ModuleOut(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    archived: bool
    created_at: datetime
    updated_at: datetime


class TopicOut(BaseModel):
    id: UUID
    project_id: UUID
    module_id: UUID
    title: str
    archived: bool
    created_at: datetime
    updated_at: datetime


class ItemOut(BaseModel):
    id: UUID
    project_id: UUID
    topic_id: UUID
    type: ItemType
    prompt: str
    sample_answer: str | None
    translation: str | None
    keywords: list[str]
    tags: list[str]
    follow_up_questions: list[str]
    difficulty: int | None
    archived: bool
    created_at: datetime
    updated_at: datetime


def module_out(m: ModuleRecord) -> ModuleOut:
    return ModuleOut(
        id=m.id,
        project_id=m.project_id,
        title=m.title,
        archived=m.archived,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def topic_out(t: TopicRecord) -> TopicOut:
    return TopicOut(
        id=t.id,
        project_id=t.project_id,
        module_id=t.module_id,
        title=t.title,
        archived=t.archived,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def item_out(i: ItemRecord) -> ItemOut:
    return ItemOut(
        id=i.id,
        project_id=i.project_id,
        topic_id=i.topic_id,
        type=i.type,
        prompt=i.prompt,
        sample_answer=i.sample_answer,
        translation=i.translation,
        keywords=i.keywords,
        tags=i.tags,
        follow_up_questions=i.follow_up_questions,
        difficulty=i.difficulty,
        archived=i.archived,
        created_at=i.created_at,
        updated_at=i.updated_at,
    )


# routes -------------------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/projects/{project_id}", dependencies=[Depends(verify_origin)])

Reader = Annotated[Principal, Depends(principal_dependency)]
Writer = Annotated[Principal, Depends(csrf_principal_dependency)]
Db = Annotated[Session, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]
Cursor = Annotated[str | None, Query(max_length=200)]


@router.post("/modules", status_code=201)
def create_module(
    project_id: UUID, body: ModuleCreate, principal: Writer, db: Db, now: Now
) -> ModuleOut:
    return module_out(application.create_module(db, principal, project_id, body.title, now))


@router.get("/modules")
def list_modules(
    project_id: UUID,
    principal: Reader,
    db: Db,
    limit: PageLimit = 50,
    cursor: Cursor = None,
    include_archived: bool = False,
) -> Page[ModuleOut]:
    rows, next_cursor = application.list_modules(
        db, principal, project_id, cursor=cursor, limit=limit, include_archived=include_archived
    )
    return Page[ModuleOut](items=[module_out(r) for r in rows], next_cursor=next_cursor)


@router.get("/modules/{module_id}")
def get_module(project_id: UUID, module_id: UUID, principal: Reader, db: Db) -> ModuleOut:
    return module_out(application.get_module(db, principal, project_id, module_id))


@router.patch("/modules/{module_id}")
def update_module(
    project_id: UUID, module_id: UUID, body: ModuleUpdate, principal: Writer, db: Db, now: Now
) -> ModuleOut:
    changes = body.changes()
    return module_out(application.update_module(db, principal, project_id, module_id, changes, now))


@router.delete("/modules/{module_id}", status_code=204)
def archive_module(
    project_id: UUID, module_id: UUID, principal: Writer, db: Db, now: Now
) -> Response:
    application.archive_module(db, principal, project_id, module_id, now)
    return Response(status_code=204)


@router.post("/topics", status_code=201)
def create_topic(
    project_id: UUID, body: TopicCreate, principal: Writer, db: Db, now: Now
) -> TopicOut:
    topic = application.create_topic(db, principal, project_id, body.module_id, body.title, now)
    return topic_out(topic)


@router.get("/topics")
def list_topics(
    project_id: UUID,
    principal: Reader,
    db: Db,
    module_id: UUID | None = None,
    limit: PageLimit = 50,
    cursor: Cursor = None,
    include_archived: bool = False,
) -> Page[TopicOut]:
    rows, next_cursor = application.list_topics(
        db,
        principal,
        project_id,
        module_id=module_id,
        cursor=cursor,
        limit=limit,
        include_archived=include_archived,
    )
    return Page[TopicOut](items=[topic_out(r) for r in rows], next_cursor=next_cursor)


@router.get("/topics/{topic_id}")
def get_topic(project_id: UUID, topic_id: UUID, principal: Reader, db: Db) -> TopicOut:
    return topic_out(application.get_topic(db, principal, project_id, topic_id))


@router.patch("/topics/{topic_id}")
def update_topic(
    project_id: UUID, topic_id: UUID, body: TopicUpdate, principal: Writer, db: Db, now: Now
) -> TopicOut:
    return topic_out(
        application.update_topic(db, principal, project_id, topic_id, body.changes(), now)
    )


@router.delete("/topics/{topic_id}", status_code=204)
def archive_topic(
    project_id: UUID, topic_id: UUID, principal: Writer, db: Db, now: Now
) -> Response:
    application.archive_topic(db, principal, project_id, topic_id, now)
    return Response(status_code=204)


@router.post("/items", status_code=201)
def create_item(project_id: UUID, body: ItemCreate, principal: Writer, db: Db, now: Now) -> ItemOut:
    values = body.model_dump()
    return item_out(application.create_item(db, principal, project_id, values, now))


@router.get("/items")
def list_items(
    project_id: UUID,
    principal: Reader,
    db: Db,
    topic_id: UUID | None = None,
    limit: PageLimit = 50,
    cursor: Cursor = None,
    include_archived: bool = False,
) -> Page[ItemOut]:
    rows, next_cursor = application.list_items(
        db,
        principal,
        project_id,
        topic_id=topic_id,
        cursor=cursor,
        limit=limit,
        include_archived=include_archived,
    )
    return Page[ItemOut](items=[item_out(r) for r in rows], next_cursor=next_cursor)


@router.get("/items/{item_id}")
def get_item(project_id: UUID, item_id: UUID, principal: Reader, db: Db) -> ItemOut:
    return item_out(application.get_item(db, principal, project_id, item_id))


@router.patch("/items/{item_id}")
def update_item(
    project_id: UUID, item_id: UUID, body: ItemUpdate, principal: Writer, db: Db, now: Now
) -> ItemOut:
    return item_out(
        application.update_item(db, principal, project_id, item_id, body.changes(), now)
    )


@router.delete("/items/{item_id}", status_code=204)
def archive_item(project_id: UUID, item_id: UUID, principal: Writer, db: Db, now: Now) -> Response:
    application.archive_item(db, principal, project_id, item_id, now)
    return Response(status_code=204)
