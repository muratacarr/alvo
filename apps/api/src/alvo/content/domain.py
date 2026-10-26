"""Content domain: records, duplicate identity rules and the data an import plan hands over.

Pure logic with no framework imports. The content module owns every write to its tables;
other modules (such as imports) build a `ContentPlan` and ask this module to apply it.
"""

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

# Field limits shared by the HTTP layer and the import parser.
TITLE_MAX = 200
PROMPT_MAX = 2000
ANSWER_MAX = 10000
TRANSLATION_MAX = 2000
LABEL_MAX = 64
FOLLOW_UP_MAX = 500
MAX_KEYWORDS = 30
MAX_TAGS = 30
MAX_FOLLOW_UPS = 10
EXTERNAL_ID_MAX = 100
EXTERNAL_ID_PATTERN = r"^[A-Za-z0-9._:-]+$"


class ItemType(StrEnum):
    QUESTION = "question"
    PHRASE = "phrase"
    VOCABULARY = "vocabulary"
    CONCEPT = "concept"
    SCENARIO = "scenario"


class PracticeMode(StrEnum):
    READ_ALOUD = "read_aloud"
    SHADOWING = "shadowing"
    FILL_GAPS = "fill_gaps"
    KEYWORD_SPEAKING = "keyword_speaking"
    GUIDED_SPEAKING = "guided_speaking"
    FREE_SPEAKING = "free_speaking"
    FOLLOW_UP_CHALLENGE = "follow_up_challenge"


# --- duplicate identity -------------------------------------------------------------------

_WHITESPACE = re.compile(r"\s+")


def _strict_form(value: str) -> str:
    """NFKC, collapsed whitespace, case-folded: what "exactly the same text" means."""
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value)).strip().casefold()


def item_fingerprint(item_type: ItemType, prompt: str) -> str:
    """Exact-duplicate identity: item type plus the strictly normalised prompt."""
    return hashlib.sha256(f"{item_type.value}\n{_strict_form(prompt)}".encode()).hexdigest()


def loose_key(prompt: str) -> str:
    """Near-duplicate identity: also ignores accents and punctuation. Used only to flag."""
    decomposed = unicodedata.normalize("NFKD", prompt)
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    kept = "".join(c for c in without_marks.casefold() if c.isalnum() or c.isspace())
    return hashlib.sha256(_WHITESPACE.sub(" ", kept).strip().encode()).hexdigest()


def title_key(title: str) -> str:
    """Modules and topics with the same key are treated as the same container."""
    return _strict_form(title)


# --- records ------------------------------------------------------------------------------


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
    external_id: str | None
    practice_modes: list[str]
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    @property
    def archived(self) -> bool:
        return self.archived_at is not None


# --- import hand-over ---------------------------------------------------------------------


@dataclass(frozen=True)
class ItemFields:
    """User-authored item content, as parsed from an import file."""

    external_id: str | None
    type: ItemType
    prompt: str
    sample_answer: str | None = None
    translation: str | None = None
    keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)
    difficulty: int | None = None
    practice_modes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DedupeIndex:
    """What already exists in a project, as far as duplicate detection is concerned.

    Items include archived ones: an archived item still reserves its identity so that an
    import never resurrects it. Modules and topics contain only live containers.
    """

    external_ids: set[str]
    fingerprints: set[str]
    loose_keys: dict[tuple[str, str], str]  # (item type, loose key) -> an existing prompt
    modules: dict[str, UUID]  # title key -> id
    topics: dict[tuple[UUID, str], UUID]  # (module id, title key) -> id


@dataclass(frozen=True)
class PlannedItem:
    fields: ItemFields
    fingerprint: str
    loose: str


@dataclass
class PlannedTopic:
    title: str
    existing_id: UUID | None
    items: list[PlannedItem] = field(default_factory=list)


@dataclass
class PlannedModule:
    title: str
    existing_id: UUID | None
    topics: list[PlannedTopic] = field(default_factory=list)


@dataclass
class ContentPlan:
    modules: list[PlannedModule] = field(default_factory=list)


@dataclass(frozen=True)
class ApplyResult:
    created_modules: int
    created_topics: int
    inserted_items: int
    skipped_items: int  # lost a race against a concurrent writer; nothing was overwritten
