"""Content domain records: the Project -> Module -> Topic -> Learning item hierarchy."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ItemType(StrEnum):
    QUESTION = "question"
    PHRASE = "phrase"
    VOCABULARY = "vocabulary"
    CONCEPT = "concept"
    SCENARIO = "scenario"


@dataclass(frozen=True)
class ModuleRecord:
    id: UUID
    project_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    @property
    def archived(self) -> bool:
        return self.archived_at is not None


@dataclass(frozen=True)
class TopicRecord:
    id: UUID
    project_id: UUID
    module_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    @property
    def archived(self) -> bool:
        return self.archived_at is not None


@dataclass(frozen=True)
class ItemRecord:
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
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    @property
    def archived(self) -> bool:
        return self.archived_at is not None
