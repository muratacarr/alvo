"""Strict parser for the import file (schema version 1.0).

Anything that makes the whole file untrustworthy (not JSON, repeated keys, unknown version
or fields, too large) raises `ImportRejected`. A single bad item does not: it is recorded as
an invalid entry (path and reason codes only, never the submitted values) so the user can
see all problems at once.
"""

import hashlib
import json
import re
from importlib import resources
from typing import Annotated, Any, NoReturn

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
)

from alvo.content.domain import (
    ANSWER_MAX,
    EXTERNAL_ID_MAX,
    EXTERNAL_ID_PATTERN,
    FOLLOW_UP_MAX,
    LABEL_MAX,
    MAX_FOLLOW_UPS,
    MAX_KEYWORDS,
    MAX_TAGS,
    PROMPT_MAX,
    TITLE_MAX,
    TRANSLATION_MAX,
    ItemFields,
    ItemType,
    PracticeMode,
)
from alvo.imports.domain import (
    ImportRejected,
    InvalidEntry,
    ParsedDocument,
    ParsedItem,
    ParsedModule,
    ParsedTopic,
)
from alvo.shared.text import CLEAN, clean_text

__all__ = [
    "MAX_ITEMS",
    "MAX_MODULES",
    "MAX_TOPICS_PER_MODULE",
    "SUPPORTED_VERSIONS",
    "ImportRejected",
    "load_sample_document",
    "load_schema",
    "parse_document",
    "template_bytes",
]

MAX_ITEMS = 2000
MAX_MODULES = 100
MAX_TOPICS_PER_MODULE = 200
SUPPORTED_VERSIONS = ["1.0"]

_LANGUAGE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


Prompt = Annotated[str, CLEAN, StringConstraints(min_length=1, max_length=PROMPT_MAX)]
SampleAnswer = Annotated[str, CLEAN, StringConstraints(min_length=1, max_length=ANSWER_MAX)]
Translation = Annotated[str, CLEAN, StringConstraints(min_length=1, max_length=TRANSLATION_MAX)]
Label = Annotated[str, CLEAN, StringConstraints(min_length=1, max_length=LABEL_MAX)]
FollowUp = Annotated[str, CLEAN, StringConstraints(min_length=1, max_length=FOLLOW_UP_MAX)]
ExternalId = Annotated[
    str, StringConstraints(pattern=EXTERNAL_ID_PATTERN, max_length=EXTERNAL_ID_MAX)
]


class _Practice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modes: Annotated[list[PracticeMode], Field(max_length=len(PracticeMode))] = Field(
        default_factory=list
    )

    @field_validator("modes")
    @classmethod
    def _unique(cls, value: list[PracticeMode]) -> list[PracticeMode]:
        if len(set(value)) != len(value):
            raise ValueError("modes must be unique")
        return value


class _Item(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: ExternalId | None = Field(default=None, alias="externalId")
    type: ItemType
    prompt: Prompt
    sample_answer: SampleAnswer | None = Field(default=None, alias="sampleAnswer")
    translation: Translation | None = None
    keywords: Annotated[list[Label], Field(max_length=MAX_KEYWORDS)] = Field(default_factory=list)
    tags: Annotated[list[Label], Field(max_length=MAX_TAGS)] = Field(default_factory=list)
    follow_up_questions: Annotated[list[FollowUp], Field(max_length=MAX_FOLLOW_UPS)] = Field(
        default_factory=list, alias="followUpQuestions"
    )
    difficulty: Annotated[int, Field(strict=True, ge=1, le=5)] | None = None
    practice: _Practice | None = None

    def to_fields(self) -> ItemFields:
        return ItemFields(
            external_id=self.external_id,
            type=self.type,
            prompt=self.prompt,
            sample_answer=self.sample_answer,
            translation=self.translation,
            keywords=list(self.keywords),
            tags=list(self.tags),
            follow_up_questions=list(self.follow_up_questions),
            difficulty=self.difficulty,
            practice_modes=[m.value for m in self.practice.modes] if self.practice else [],
        )


class _DuplicateKey(Exception):
    pass


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


def _reject_constant(name: str) -> NoReturn:
    raise ValueError(f"{name} is not valid JSON")


def _fail(code: str, **details: Any) -> NoReturn:
    raise ImportRejected(code, details)


def _load_json(raw: bytes) -> Any:
    try:
        text = raw.decode("utf-8")
        return json.loads(
            text, object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant
        )
    except _DuplicateKey:
        _fail("duplicate_key")
    except RecursionError:
        _fail("too_deep")
    except ValueError:  # includes UnicodeDecodeError and JSONDecodeError
        _fail("invalid_json")


def _only_keys(obj: dict[str, Any], allowed: set[str], required: set[str]) -> None:
    if set(obj) - allowed or required - set(obj):
        _fail("invalid_document")


def _title(value: Any) -> str:
    if not isinstance(value, str):
        _fail("invalid_document")
    try:
        cleaned = clean_text(value)
    except ValueError:
        _fail("invalid_document")
    if not 1 <= len(cleaned) <= TITLE_MAX:
        _fail("invalid_document")
    return cleaned


def _as_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        _fail("invalid_document")
    return value


def _as_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("invalid_document")
    return value


def _digest(document: Any) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _validate_item(path: str, raw_item: Any) -> tuple[ParsedItem | None, InvalidEntry | None]:
    if not isinstance(raw_item, dict):
        return None, InvalidEntry(path, ["not_an_object"])
    try:
        model = _Item.model_validate(raw_item)
    except ValidationError as exc:
        reasons = [f"{'.'.join(str(p) for p in e['loc'])}:{e['type']}" for e in exc.errors()]
        return None, InvalidEntry(path, reasons)
    return ParsedItem(path, model.to_fields()), None


def parse_document(raw: bytes) -> ParsedDocument:
    document = _as_dict(_load_json(raw))

    if "schemaVersion" not in document:
        _fail("schema_version_missing")
    version = document["schemaVersion"]
    if not isinstance(version, str) or version not in SUPPORTED_VERSIONS:
        _fail("unsupported_schema_version", supported=SUPPORTED_VERSIONS)
    _only_keys(document, {"schemaVersion", "program"}, {"schemaVersion", "program"})

    program = _as_dict(document["program"])
    _only_keys(program, {"title", "targetLanguage", "level", "modules"}, {"title", "modules"})
    program_title = _title(program["title"])
    language = program.get("targetLanguage")
    if language is not None and not (
        isinstance(language, str) and len(language) <= 35 and _LANGUAGE.match(language)
    ):
        _fail("invalid_document")
    level = program.get("level")
    if level is not None:
        level = (
            _title(level)
            if isinstance(level, str) and len(level) <= 32
            else _fail("invalid_document")
        )

    raw_modules = _as_list(program["modules"])
    if len(raw_modules) > MAX_MODULES:
        _fail("too_many_modules", limit=MAX_MODULES)

    total_items = 0
    for raw_module in raw_modules:
        module = _as_dict(raw_module)
        _only_keys(module, {"title", "topics"}, {"title", "topics"})
        topics = _as_list(module["topics"])
        if len(topics) > MAX_TOPICS_PER_MODULE:
            _fail("too_many_topics", limit=MAX_TOPICS_PER_MODULE)
        for raw_topic in topics:
            topic = _as_dict(raw_topic)
            _only_keys(topic, {"title", "items"}, {"title", "items"})
            total_items += len(_as_list(topic["items"]))
            if total_items > MAX_ITEMS:
                _fail("too_many_items", limit=MAX_ITEMS)

    modules: list[ParsedModule] = []
    invalid: list[InvalidEntry] = []
    for m_index, raw_module in enumerate(raw_modules):
        topics_out: list[ParsedTopic] = []
        for t_index, raw_topic in enumerate(raw_module["topics"]):
            items_out: list[ParsedItem] = []
            for i_index, raw_item in enumerate(raw_topic["items"]):
                path = f"modules[{m_index}].topics[{t_index}].items[{i_index}]"
                parsed, problem = _validate_item(path, raw_item)
                if parsed:
                    items_out.append(parsed)
                if problem:
                    invalid.append(problem)
            topics_out.append(ParsedTopic(_title(raw_topic["title"]), items_out))
        modules.append(ParsedModule(_title(raw_module["title"]), topics_out))

    return ParsedDocument(
        program_title=program_title,
        target_language=language,
        level=level,
        modules=modules,
        invalid=invalid,
        digest=_digest(document),
    )


# published templates ------------------------------------------------------------------------


def template_bytes(name: str) -> bytes:
    return (resources.files("alvo.imports") / "templates" / name).read_bytes()


def load_schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(template_bytes("import-schema-v1.json"))
    return schema


def load_sample_document() -> dict[str, Any]:
    sample: dict[str, Any] = json.loads(template_bytes("import-sample-v1.json"))
    return sample
