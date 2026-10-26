"""Import use cases: preview, commit (atomic and idempotent) and export.

Ownership is checked first through the projects module. Writes are delegated to the content
module; this module only parses, plans, records the job and coordinates the transaction.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from alvo.content.application import apply_content_plan, export_tree, load_dedupe_index
from alvo.content.domain import ItemRecord
from alvo.identity.domain import Principal
from alvo.imports.domain import (
    AmbiguousPolicy,
    ImportCounts,
    ImportPlan,
    ImportRejected,
    ParsedDocument,
    plan_import,
)
from alvo.imports.infrastructure import SqlImportStore
from alvo.imports.parsing import parse_document
from alvo.projects.application import require_project
from alvo.shared.errors import ApiError

audit = logging.getLogger("alvo.audit")


@dataclass(frozen=True)
class PreviewResult:
    program_title: str
    plan: ImportPlan


@dataclass(frozen=True)
class CommitResult:
    job_id: UUID
    replayed: bool
    counts: dict[str, int]


def _parse(raw: bytes) -> ParsedDocument:
    try:
        return parse_document(raw)
    except ImportRejected as exc:
        raise ApiError(422, exc.code, dict(exc.details)) from exc


def preview(
    db: Session,
    principal: Principal,
    project_id: UUID,
    raw: bytes,
    ambiguous: AmbiguousPolicy,
) -> PreviewResult:
    """Read-only: nothing is written, not even a job record."""
    require_project(db, principal, project_id)
    document = _parse(raw)
    plan = plan_import(document, load_dedupe_index(db, project_id), ambiguous)
    return PreviewResult(document.program_title, plan)


def commit(
    db: Session,
    principal: Principal,
    project_id: UUID,
    raw: bytes,
    *,
    idempotency_key: str,
    ambiguous: AmbiguousPolicy,
    commits_per_hour: int,
    now: datetime,
) -> CommitResult:
    require_project(db, principal, project_id, writable=True)
    document = _parse(raw)
    if document.invalid:
        raise ApiError(422, "invalid_items", {"count": len(document.invalid)})

    store = SqlImportStore(db)
    store.lock_project(project_id)  # released when this transaction ends
    store.limit_statement_time()

    existing = store.find_job(project_id, idempotency_key)
    if existing is not None:
        db.rollback()
        if existing.source_digest != document.digest:
            raise ApiError(409, "idempotency_key_reuse")
        return CommitResult(existing.id, True, existing.counts)

    if store.commits_since(principal.user_id, now - timedelta(hours=1)) >= commits_per_hour:
        db.rollback()
        raise ApiError(429, "rate_limited")

    job_id = store.create_job(
        project_id=project_id,
        owner_id=principal.user_id,
        key=idempotency_key,
        digest=document.digest,
        now=now,
    )
    # Planned against the committed state *after* taking the lock, so a concurrent import
    # that finished first is already visible and its items count as duplicates.
    plan = plan_import(document, load_dedupe_index(db, project_id), ambiguous)
    applied = apply_content_plan(db, project_id, plan.content, now)

    counts = plan.counts
    final = ImportCounts(
        new_items=applied.inserted_items,
        new_modules=applied.created_modules,
        new_topics=applied.created_topics,
        duplicate_external_id=counts.duplicate_external_id,
        duplicate_content=counts.duplicate_content + applied.skipped_items,
        duplicate_in_file=counts.duplicate_in_file,
        ambiguous=counts.ambiguous,
        invalid=0,
    ).as_dict()
    store.finish_job(job_id, final, now)
    db.commit()
    audit.info(
        "event=import_committed user_id=%s project_id=%s job_id=%s new_items=%s",
        principal.user_id,
        project_id,
        job_id,
        final["new_items"],
    )
    return CommitResult(job_id, False, final)


# export ------------------------------------------------------------------------------------


def _export_item(item: ItemRecord) -> dict[str, Any]:
    """Only user-authored content, and only the fields that are set."""
    entry: dict[str, Any] = {}
    if item.external_id:
        entry["externalId"] = item.external_id
    entry["type"] = item.type.value
    entry["prompt"] = item.prompt
    if item.sample_answer:
        entry["sampleAnswer"] = item.sample_answer
    if item.translation:
        entry["translation"] = item.translation
    if item.keywords:
        entry["keywords"] = item.keywords
    if item.tags:
        entry["tags"] = item.tags
    if item.follow_up_questions:
        entry["followUpQuestions"] = item.follow_up_questions
    if item.difficulty is not None:
        entry["difficulty"] = item.difficulty
    if item.practice_modes:
        entry["practice"] = {"modes": item.practice_modes}
    return entry


def export_project(db: Session, principal: Principal, project_id: UUID) -> dict[str, Any]:
    project = require_project(db, principal, project_id)
    modules = [
        {
            "title": module.title,
            "topics": [
                {"title": topic.title, "items": [_export_item(i) for i in items]}
                for topic, items in topics
            ],
        }
        for module, topics in export_tree(db, project_id)
    ]
    return {
        "schemaVersion": "1.0",
        "program": {"title": project.title, "targetLanguage": "en", "modules": modules},
    }
