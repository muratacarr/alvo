"""HTTP transport for imports, exports and the published templates.

The import body *is* the document, read as raw bytes so that duplicate JSON keys and
nesting can be judged by our own strict parser instead of the framework's lenient one.
"""

import json
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from alvo.identity.api import csrf_principal_dependency, get_db, principal_dependency, verify_origin
from alvo.identity.domain import Principal
from alvo.imports import application
from alvo.imports.domain import ImportPlan
from alvo.imports.parsing import template_bytes
from alvo.shared.http import get_now

_LIST_LIMIT = 50
_PROMPT_PREVIEW = 200

Reader = Annotated[Principal, Depends(principal_dependency)]
Writer = Annotated[Principal, Depends(csrf_principal_dependency)]
Db = Annotated[Session, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]
AmbiguousMode = Annotated[Literal["skip", "add"], Query()]
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
]


class SampleOut(BaseModel):
    path: str
    type: str
    prompt: str


class AmbiguousOut(BaseModel):
    path: str
    prompt: str
    existing_prompt: str


class InvalidOut(BaseModel):
    path: str
    reasons: list[str]


class PreviewOut(BaseModel):
    program_title: str
    counts: dict[str, int]
    new_samples: list[SampleOut]
    ambiguous: list[AmbiguousOut]
    invalid: list[InvalidOut]


class CommitOut(BaseModel):
    job_id: UUID
    replayed: bool
    counts: dict[str, int]


def _clip(text: str) -> str:
    return text if len(text) <= _PROMPT_PREVIEW else text[:_PROMPT_PREVIEW] + "…"


def _preview_out(program_title: str, plan: ImportPlan) -> PreviewOut:
    return PreviewOut(
        program_title=program_title,
        counts=plan.counts.as_dict(),
        new_samples=[
            SampleOut(path=s.path, type=s.type, prompt=_clip(s.prompt)) for s in plan.new_samples
        ],
        ambiguous=[
            AmbiguousOut(
                path=a.path, prompt=_clip(a.prompt), existing_prompt=_clip(a.existing_prompt)
            )
            for a in plan.ambiguous[:_LIST_LIMIT]
        ],
        invalid=[InvalidOut(path=i.path, reasons=i.reasons) for i in plan.invalid[:_LIST_LIMIT]],
    )


router = APIRouter(prefix="/api/v1", dependencies=[Depends(verify_origin)])


@router.post("/projects/{project_id}/imports/preview")
async def preview_import(
    project_id: UUID,
    request: Request,
    principal: Writer,
    db: Db,
    ambiguous: AmbiguousMode = "skip",
) -> PreviewOut:
    raw = await request.body()
    result = await run_in_threadpool(application.preview, db, principal, project_id, raw, ambiguous)
    return _preview_out(result.program_title, result.plan)


@router.post("/projects/{project_id}/imports/commit")
async def commit_import(
    project_id: UUID,
    request: Request,
    principal: Writer,
    db: Db,
    now: Now,
    idempotency_key: IdempotencyKey,
    ambiguous: AmbiguousMode = "skip",
) -> CommitOut:
    raw = await request.body()
    limit: int = request.app.state.settings.import_commits_per_hour
    result = await run_in_threadpool(
        lambda: application.commit(
            db,
            principal,
            project_id,
            raw,
            idempotency_key=idempotency_key,
            ambiguous=ambiguous,
            commits_per_hour=limit,
            now=now,
        )
    )
    return CommitOut(job_id=result.job_id, replayed=result.replayed, counts=result.counts)


@router.get("/projects/{project_id}/export")
def export_project(project_id: UUID, principal: Reader, db: Db) -> Response:
    document: dict[str, Any] = application.export_project(db, principal, project_id)
    return Response(
        content=json.dumps(document, ensure_ascii=False, indent=2).encode(),
        media_type="application/json",
        headers={
            # A fixed name: user-controlled text never goes into a response header.
            "Content-Disposition": 'attachment; filename="alvo-export.json"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/templates/import/v1/schema")
def import_schema() -> Response:
    return Response(content=template_bytes("import-schema-v1.json"), media_type="application/json")


@router.get("/templates/import/v1/sample")
def import_sample() -> Response:
    return Response(content=template_bytes("import-sample-v1.json"), media_type="application/json")
