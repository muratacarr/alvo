"""Import domain: the parsed document, and the planner that decides what to add.

`plan_import` is the whole ADD_NEW_ONLY policy in one pure function. It never updates or
removes anything: it only decides which new items (and the containers they need) to create.
"""

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from alvo.content.domain import (
    ContentPlan,
    DedupeIndex,
    ItemFields,
    PlannedItem,
    PlannedModule,
    PlannedTopic,
    item_fingerprint,
    loose_key,
    title_key,
)

AmbiguousPolicy = Literal["skip", "add"]

_SAMPLE_LIMIT = 10


class ImportRejected(Exception):
    """The document as a whole cannot be used. `code` is stable and safe to show."""

    def __init__(self, code: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class ImportJob:
    id: UUID
    source_digest: str
    counts: dict[str, int]


@dataclass(frozen=True)
class InvalidEntry:
    path: str
    reasons: list[str]


@dataclass(frozen=True)
class ParsedItem:
    path: str
    fields: ItemFields


@dataclass(frozen=True)
class ParsedTopic:
    title: str
    items: list[ParsedItem]


@dataclass(frozen=True)
class ParsedModule:
    title: str
    topics: list[ParsedTopic]


@dataclass(frozen=True)
class ParsedDocument:
    program_title: str
    target_language: str | None
    level: str | None
    modules: list[ParsedModule]
    invalid: list[InvalidEntry]
    digest: str


@dataclass
class ImportCounts:
    new_items: int = 0
    new_modules: int = 0
    new_topics: int = 0
    duplicate_external_id: int = 0
    duplicate_content: int = 0
    duplicate_in_file: int = 0
    ambiguous: int = 0
    invalid: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "new_items": self.new_items,
            "new_modules": self.new_modules,
            "new_topics": self.new_topics,
            "duplicate_external_id": self.duplicate_external_id,
            "duplicate_content": self.duplicate_content,
            "duplicate_in_file": self.duplicate_in_file,
            "ambiguous": self.ambiguous,
            "invalid": self.invalid,
        }


@dataclass(frozen=True)
class Sample:
    path: str
    type: str
    prompt: str


@dataclass(frozen=True)
class AmbiguousEntry:
    path: str
    prompt: str
    existing_prompt: str


@dataclass
class ImportPlan:
    counts: ImportCounts
    content: ContentPlan
    new_samples: list[Sample] = field(default_factory=list)
    ambiguous: list[AmbiguousEntry] = field(default_factory=list)
    invalid: list[InvalidEntry] = field(default_factory=list)


def plan_import(
    document: ParsedDocument, index: DedupeIndex, ambiguous_policy: AmbiguousPolicy
) -> ImportPlan:
    counts = ImportCounts(invalid=len(document.invalid))
    plan = ImportPlan(counts=counts, content=ContentPlan(), invalid=list(document.invalid))

    seen_external: set[str] = set()
    seen_fingerprints: set[str] = set()
    seen_loose: dict[tuple[str, str], str] = {}
    modules: dict[str, PlannedModule] = {}
    topics: dict[tuple[str, str], PlannedTopic] = {}

    for module in document.modules:
        for topic in module.topics:
            for parsed in topic.items:
                fields = parsed.fields
                fingerprint = item_fingerprint(fields.type, fields.prompt)
                loose = loose_key(fields.prompt)

                if fields.external_id and fields.external_id in index.external_ids:
                    counts.duplicate_external_id += 1
                    continue
                if fields.external_id and fields.external_id in seen_external:
                    counts.duplicate_in_file += 1
                    continue
                if fingerprint in index.fingerprints:
                    counts.duplicate_content += 1
                    continue
                if fingerprint in seen_fingerprints:
                    counts.duplicate_in_file += 1
                    continue

                near = index.loose_keys.get((fields.type.value, loose)) or seen_loose.get(
                    (fields.type.value, loose)
                )
                if near is not None:
                    counts.ambiguous += 1
                    plan.ambiguous.append(AmbiguousEntry(parsed.path, fields.prompt, near))
                    if ambiguous_policy == "skip":
                        continue

                if fields.external_id:
                    seen_external.add(fields.external_id)
                seen_fingerprints.add(fingerprint)
                seen_loose.setdefault((fields.type.value, loose), fields.prompt)

                planned_module = modules.get(title_key(module.title))
                if planned_module is None:
                    planned_module = PlannedModule(
                        module.title, index.modules.get(title_key(module.title))
                    )
                    modules[title_key(module.title)] = planned_module
                    plan.content.modules.append(planned_module)
                    if planned_module.existing_id is None:
                        counts.new_modules += 1
                topic_key = (title_key(module.title), title_key(topic.title))
                planned_topic = topics.get(topic_key)
                if planned_topic is None:
                    existing_topic = (
                        index.topics.get((planned_module.existing_id, title_key(topic.title)))
                        if planned_module.existing_id
                        else None
                    )
                    planned_topic = PlannedTopic(topic.title, existing_topic)
                    topics[topic_key] = planned_topic
                    planned_module.topics.append(planned_topic)
                    if existing_topic is None:
                        counts.new_topics += 1

                planned_topic.items.append(PlannedItem(fields, fingerprint, loose))
                counts.new_items += 1
                if len(plan.new_samples) < _SAMPLE_LIMIT:
                    plan.new_samples.append(Sample(parsed.path, fields.type.value, fields.prompt))
    return plan
