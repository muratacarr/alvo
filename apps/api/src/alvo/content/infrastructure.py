"""SQLAlchemy persistence for modules, topics and learning items.

Every row carries `project_id`, and composite foreign keys make the database itself reject a
topic whose module (or an item whose topic) belongs to a different project. Every query
filters by `project_id`; ownership of that project is checked by the caller.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    select,
    text,
    tuple_,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from alvo.content.domain import (
    ApplyResult,
    ContentPlan,
    DedupeIndex,
    ItemRecord,
    ItemType,
    ModuleRecord,
    TopicRecord,
    title_key,
)
from alvo.shared.orm import Base


class ModuleRow(Base):
    __tablename__ = "modules"
    __table_args__ = (UniqueConstraint("project_id", "id", name="uq_modules_project_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TopicRow(Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_topics_project_id"),
        ForeignKeyConstraint(
            ["project_id", "module_id"],
            ["modules.project_id", "modules.id"],
            name="fk_topics_module_same_project",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    module_id: Mapped[UUID] = mapped_column()
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ItemRow(Base):
    __tablename__ = "learning_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "topic_id"],
            ["topics.project_id", "topics.id"],
            name="fk_items_topic_same_project",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "type IN ('question', 'phrase', 'vocabulary', 'concept', 'scenario')",
            name="ck_items_type",
        ),
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_items_difficulty"),
        CheckConstraint(
            "cardinality(keywords) <= 30 AND cardinality(tags) <= 30 "
            "AND cardinality(follow_up_questions) <= 10",
            name="ck_items_list_sizes",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[UUID] = mapped_column()
    type: Mapped[str] = mapped_column(String(16))
    prompt: Mapped[str] = mapped_column(String(2000))
    sample_answer: Mapped[str | None] = mapped_column(Text)
    translation: Mapped[str | None] = mapped_column(String(2000))
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)), server_default=text("'{}'"), nullable=False
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)), server_default=text("'{}'"), nullable=False
    )
    follow_up_questions: Mapped[list[str]] = mapped_column(
        ARRAY(String(500)), server_default=text("'{}'"), nullable=False
    )
    difficulty: Mapped[int | None] = mapped_column(SmallInteger)
    external_id: Mapped[str | None] = mapped_column(String(100))
    fingerprint: Mapped[str] = mapped_column(String(64))
    loose_key: Mapped[str] = mapped_column(String(64))
    practice_modes: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), server_default=text("'{}'"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def _module(row: ModuleRow) -> ModuleRecord:
    return ModuleRecord(
        row.id, row.project_id, row.title, row.created_at, row.updated_at, row.archived_at
    )


def _topic(row: TopicRow) -> TopicRecord:
    return TopicRecord(
        row.id,
        row.project_id,
        row.module_id,
        row.title,
        row.created_at,
        row.updated_at,
        row.archived_at,
    )


def _item(row: ItemRow) -> ItemRecord:
    return ItemRecord(
        row.id,
        row.project_id,
        row.topic_id,
        ItemType(row.type),
        row.prompt,
        row.sample_answer,
        row.translation,
        list(row.keywords),
        list(row.tags),
        list(row.follow_up_questions),
        row.difficulty,
        row.external_id,
        list(row.practice_modes),
        row.created_at,
        row.updated_at,
        row.archived_at,
    )


class SqlContentStore:
    """All methods take `project_id` and never return rows from another project."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # generic helpers ---------------------------------------------------------------------

    def _get(self, model: Any, project_id: UUID, row_id: UUID) -> Any | None:
        return self._db.execute(
            select(model).where(model.project_id == project_id, model.id == row_id)
        ).scalar_one_or_none()

    def _list(
        self,
        model: Any,
        project_id: UUID,
        *,
        include_archived: bool,
        after: tuple[datetime, UUID] | None,
        limit: int,
        filters: tuple[Any, ...] = (),
    ) -> list[Any]:
        statement = select(model).where(model.project_id == project_id, *filters)
        if not include_archived:
            statement = statement.where(model.archived_at.is_(None))
        if after is not None:
            statement = statement.where(
                tuple_(model.created_at, model.id) > tuple_(after[0], after[1])
            )
        rows = self._db.execute(statement.order_by(model.created_at, model.id).limit(limit))
        return list(rows.scalars())

    def _update(
        self, model: Any, project_id: UUID, row_id: UUID, changes: dict[str, Any], now: datetime
    ) -> Any | None:
        row = self._get(model, project_id, row_id)
        if row is None:
            return None
        for key, value in changes.items():
            setattr(row, key, value)
        row.updated_at = now
        self._db.flush()
        return row

    def _archive(self, model: Any, project_id: UUID, row_id: UUID, now: datetime) -> bool:
        row = self._get(model, project_id, row_id)
        if row is None:
            return False
        if row.archived_at is None:
            row.archived_at = now
            row.updated_at = now
            self._db.flush()
        return True

    # modules -----------------------------------------------------------------------------

    def create_module(self, project_id: UUID, title: str, now: datetime) -> ModuleRecord:
        row = ModuleRow(
            id=uuid4(),
            project_id=project_id,
            title=title,
            created_at=now,
            updated_at=now,
            archived_at=None,
        )
        self._db.add(row)
        self._db.flush()
        return _module(row)

    def get_module(self, project_id: UUID, module_id: UUID) -> ModuleRecord | None:
        row = self._get(ModuleRow, project_id, module_id)
        return _module(row) if row else None

    def list_modules(self, project_id: UUID, **kwargs: Any) -> list[ModuleRecord]:
        return [_module(r) for r in self._list(ModuleRow, project_id, **kwargs)]

    def update_module(
        self, project_id: UUID, module_id: UUID, changes: dict[str, Any], now: datetime
    ) -> ModuleRecord | None:
        row = self._update(ModuleRow, project_id, module_id, changes, now)
        return _module(row) if row else None

    def archive_module(self, project_id: UUID, module_id: UUID, now: datetime) -> bool:
        return self._archive(ModuleRow, project_id, module_id, now)

    # topics ------------------------------------------------------------------------------

    def create_topic(
        self, project_id: UUID, module_id: UUID, title: str, now: datetime
    ) -> TopicRecord:
        row = TopicRow(
            id=uuid4(),
            project_id=project_id,
            module_id=module_id,
            title=title,
            created_at=now,
            updated_at=now,
            archived_at=None,
        )
        self._db.add(row)
        self._db.flush()
        return _topic(row)

    def get_topic(self, project_id: UUID, topic_id: UUID) -> TopicRecord | None:
        row = self._get(TopicRow, project_id, topic_id)
        return _topic(row) if row else None

    def list_topics(
        self, project_id: UUID, module_id: UUID | None = None, **kwargs: Any
    ) -> list[TopicRecord]:
        filters = (TopicRow.module_id == module_id,) if module_id else ()
        return [_topic(r) for r in self._list(TopicRow, project_id, filters=filters, **kwargs)]

    def update_topic(
        self, project_id: UUID, topic_id: UUID, changes: dict[str, Any], now: datetime
    ) -> TopicRecord | None:
        row = self._update(TopicRow, project_id, topic_id, changes, now)
        return _topic(row) if row else None

    def archive_topic(self, project_id: UUID, topic_id: UUID, now: datetime) -> bool:
        return self._archive(TopicRow, project_id, topic_id, now)

    # items -------------------------------------------------------------------------------

    def create_item(self, project_id: UUID, values: dict[str, Any], now: datetime) -> ItemRecord:
        row = ItemRow(
            id=uuid4(),
            project_id=project_id,
            created_at=now,
            updated_at=now,
            archived_at=None,
            **values,
        )
        self._db.add(row)
        self._db.flush()
        return _item(row)

    def get_item(self, project_id: UUID, item_id: UUID) -> ItemRecord | None:
        row = self._get(ItemRow, project_id, item_id)
        return _item(row) if row else None

    def list_items(
        self, project_id: UUID, topic_id: UUID | None = None, **kwargs: Any
    ) -> list[ItemRecord]:
        filters = (ItemRow.topic_id == topic_id,) if topic_id else ()
        return [_item(r) for r in self._list(ItemRow, project_id, filters=filters, **kwargs)]

    def update_item(
        self, project_id: UUID, item_id: UUID, changes: dict[str, Any], now: datetime
    ) -> ItemRecord | None:
        row = self._update(ItemRow, project_id, item_id, changes, now)
        return _item(row) if row else None

    def archive_item(self, project_id: UUID, item_id: UUID, now: datetime) -> bool:
        return self._archive(ItemRow, project_id, item_id, now)

    # duplicate detection, bulk apply and export ---------------------------------------------

    def load_dedupe_index(self, project_id: UUID) -> DedupeIndex:
        items = self._db.execute(
            select(
                ItemRow.external_id,
                ItemRow.fingerprint,
                ItemRow.loose_key,
                ItemRow.type,
                ItemRow.prompt,
            ).where(ItemRow.project_id == project_id)
        )
        external_ids: set[str] = set()
        fingerprints: set[str] = set()
        loose: dict[tuple[str, str], str] = {}
        for external_id, fingerprint, loose_key, item_type, prompt in items:
            if external_id:
                external_ids.add(external_id)
            fingerprints.add(fingerprint)
            loose.setdefault((item_type, loose_key), prompt)
        modules: dict[str, UUID] = {}
        for module in self._db.execute(
            select(ModuleRow.id, ModuleRow.title)
            .where(ModuleRow.project_id == project_id, ModuleRow.archived_at.is_(None))
            .order_by(ModuleRow.created_at, ModuleRow.id)
        ):
            modules.setdefault(title_key(module.title), module.id)
        topics: dict[tuple[UUID, str], UUID] = {}
        for topic in self._db.execute(
            select(TopicRow.id, TopicRow.module_id, TopicRow.title)
            .where(TopicRow.project_id == project_id, TopicRow.archived_at.is_(None))
            .order_by(TopicRow.created_at, TopicRow.id)
        ):
            topics.setdefault((topic.module_id, title_key(topic.title)), topic.id)
        return DedupeIndex(external_ids, fingerprints, loose, modules, topics)

    def apply_plan(self, project_id: UUID, plan: ContentPlan, now: datetime) -> ApplyResult:
        """Create the planned containers and items. Existing rows are never touched.

        Items use ON CONFLICT DO NOTHING, so a concurrent writer that got there first wins
        and nothing is overwritten. Timestamps advance by a microsecond per row so the order
        of the file is the order of listing.
        """
        created_modules = created_topics = inserted = skipped = 0
        tick = 0

        def stamp() -> datetime:
            nonlocal tick
            tick += 1
            return now + timedelta(microseconds=tick)

        for planned_module in plan.modules:
            module_id = planned_module.existing_id
            if module_id is None:
                module_id = self.create_module(project_id, planned_module.title, stamp()).id
                created_modules += 1
            for planned_topic in planned_module.topics:
                topic_id = planned_topic.existing_id
                if topic_id is None:
                    topic_id = self.create_topic(
                        project_id, module_id, planned_topic.title, stamp()
                    ).id
                    created_topics += 1
                rows = []
                for planned in planned_topic.items:
                    fields, moment = planned.fields, stamp()
                    rows.append(
                        {
                            "id": uuid4(),
                            "project_id": project_id,
                            "topic_id": topic_id,
                            "type": fields.type.value,
                            "prompt": fields.prompt,
                            "sample_answer": fields.sample_answer,
                            "translation": fields.translation,
                            "keywords": fields.keywords,
                            "tags": fields.tags,
                            "follow_up_questions": fields.follow_up_questions,
                            "difficulty": fields.difficulty,
                            "external_id": fields.external_id,
                            "fingerprint": planned.fingerprint,
                            "loose_key": planned.loose,
                            "practice_modes": fields.practice_modes,
                            "created_at": moment,
                            "updated_at": moment,
                            "archived_at": None,
                        }
                    )
                for start in range(0, len(rows), 500):
                    chunk = rows[start : start + 500]
                    # RETURNING tells us exactly which rows were inserted (DO NOTHING skips the
                    # rest), unlike rowcount, which is unreliable for multi-row ORM inserts.
                    returned = self._db.execute(
                        insert(ItemRow).values(chunk).on_conflict_do_nothing().returning(ItemRow.id)
                    ).all()
                    done = len(returned)
                    inserted += done
                    skipped += len(chunk) - done
        return ApplyResult(created_modules, created_topics, inserted, skipped)

    def export_tree(
        self, project_id: UUID
    ) -> list[tuple[ModuleRecord, list[tuple[TopicRecord, list[ItemRecord]]]]]:
        """Live content only, in creation order: archived modules, topics, items are skipped."""
        everything = {"include_archived": False, "after": None, "limit": 10**6}
        modules = self.list_modules(project_id, **everything)
        topics = self.list_topics(project_id, None, **everything)
        items = self.list_items(project_id, None, **everything)
        by_topic: dict[UUID, list[ItemRecord]] = {}
        for item in items:
            by_topic.setdefault(item.topic_id, []).append(item)
        by_module: dict[UUID, list[tuple[TopicRecord, list[ItemRecord]]]] = {}
        for topic in topics:
            by_module.setdefault(topic.module_id, []).append((topic, by_topic.get(topic.id, [])))
        return [(m, by_module.get(m.id, [])) for m in modules]
