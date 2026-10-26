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
