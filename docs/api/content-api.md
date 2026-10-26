# Content API (v1)

All routes require a session cookie. Unsafe methods (`POST`, `PATCH`, `DELETE`) also require the `Origin` header to equal the configured public origin and the `X-CSRF-Token` header (from login or `GET /api/v1/auth/csrf`). Bodies are limited to `max_request_bytes` (default 1 MiB). Unknown body fields are rejected.

Errors are `{"error": "<code>"}`: `unauthenticated` (401), `forbidden` (403), `not_found` (404, also for other users' resources), `archived` (409), `payload_too_large` (413), `invalid_request` with a `fields` list (422, never echoes values), `invalid_cursor` (422).

Lists return `{"items": [...], "next_cursor": "..." | null}`, ordered by creation time, `limit` 1-100 (default 50), `include_archived=false` by default.

| Method and path | Purpose |
|---|---|
| `POST /api/v1/projects` | Create (`title`, optional `description`) |
| `GET /api/v1/projects` | List own projects |
| `GET/PATCH/DELETE /api/v1/projects/{id}` | Read, update, archive |
| `POST /api/v1/projects/{id}/unarchive` | Restore |
| `POST/GET /api/v1/projects/{id}/modules` | Create / list modules |
| `GET/PATCH/DELETE /api/v1/projects/{id}/modules/{mid}` | Read, update, archive |
| `POST/GET /api/v1/projects/{id}/topics` | Create (`module_id`, `title`) / list (`?module_id=`) |
| `GET/PATCH/DELETE /api/v1/projects/{id}/topics/{tid}` | Read, update (can move with `module_id`), archive |
| `POST/GET /api/v1/projects/{id}/items` | Create / list (`?topic_id=`) |
| `GET/PATCH/DELETE /api/v1/projects/{id}/items/{iid}` | Read, update (can move with `topic_id`), archive |

Item fields: `topic_id`, `type` (`question`, `phrase`, `vocabulary`, `concept`, `scenario`), `prompt` (1-2000), `sample_answer` (up to 10000), `translation` (up to 2000), `keywords` / `tags` (up to 30 items of 1-64 chars), `follow_up_questions` (up to 10 items of 1-500 chars), `difficulty` (1-5).

Text is stored as entered; control characters and bidirectional override characters are rejected. Clients must render all text as plain text, never as HTML.

## Import and export

Files follow the versioned contract in `import-schema-v1.json` (JSON Schema, draft 2020-12); `import-sample-v1.json` is a complete example. Both can be downloaded without signing in from `GET /api/v1/templates/import/v1/schema` and `.../sample`. The files in `docs/api/` are kept byte-identical to the ones the API serves (a test enforces it).

| Method and path | Purpose |
|---|---|
| `POST /api/v1/projects/{id}/imports/preview[?ambiguous=skip\|add]` | Body is the document. Reports counts, samples, ambiguous and invalid entries. Writes nothing. |
| `POST /api/v1/projects/{id}/imports/commit[?ambiguous=skip\|add]` | Same body plus a required `Idempotency-Key` header (1-64 of `A-Za-z0-9_-`). Atomic. Returns `{job_id, replayed, counts}`. |
| `GET /api/v1/projects/{id}/export` | The project's live content in the same schema, as `alvo-export.json`. |

Counts: `new_items`, `new_modules`, `new_topics`, `duplicate_external_id`, `duplicate_content`, `duplicate_in_file`, `ambiguous`, `invalid`.

Import errors (`422` unless noted): `invalid_json`, `duplicate_key`, `too_deep`, `invalid_document`, `schema_version_missing`, `unsupported_schema_version` (with `supported`), `too_many_modules`, `too_many_topics`, `too_many_items`, `invalid_items` (with `count`; commit only). Also `413 payload_too_large`, `409 idempotency_key_reuse`, `409 archived`, `429 rate_limited`.

Limits: body 2 MiB, 2000 items, 100 modules, 200 topics per module, 15 s of database time, 30 commits per user per hour (all configurable except the structural ones). Only additions are made: nothing that exists is changed, and archived items are never restored.
