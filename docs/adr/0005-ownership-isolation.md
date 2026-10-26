# ADR 0005: Ownership isolation for content (BOLA prevention)

Status: Accepted (slice 1C)

## Context
Alvo stores private learning content per user. The most likely serious flaw in such an API is broken object-level authorization: a user reading or changing another user's project, module, topic or item by guessing or reusing an id. Random UUIDs do not replace authorization.

## Decision
1. **Single ownership gate.** `projects.application.require_project` is the only place that decides ownership. Every content operation calls it first. The owner filter is part of the SQL query, so a foreign id and a missing id are indistinguishable.
2. **Uniform 404.** Foreign and non-existent resources return the same `404 {"error":"not_found"}`. Archived projects return `409 {"error":"archived"}` for writes, but only to their owner.
3. **Server-derived owner.** `owner_id` is never read from a request body; request models forbid extra fields, so smuggled `owner_id`, `project_id` or `id` values are rejected.
4. **Project-scoped rows.** Modules, topics and items carry `project_id`, and every query filters by it. A resource id is only valid inside the project path it belongs to.
5. **Database as the second line of defence.** Composite foreign keys `(project_id, module_id)` and `(project_id, topic_id)` make PostgreSQL reject a child whose parent is in another project, including after a move. A test inserts such rows directly and expects an integrity error.
6. **Two-user matrix test** covers every content endpoint (all 19 calls) with a second user and asserts a uniform 404 and that nothing changed.
7. **Module boundaries** (identity, projects, content, entitlements, shared) are enforced by `import-linter` contracts that run in the test suite.

## Consequences
- One extra query per request for the ownership check.
- Archiving does not cascade: children of an archived module stay readable by id, but new children cannot be attached to an archived parent (`409`).
- Restoring archived modules, topics and items is not implemented yet (only projects can be unarchived).
- Text is stored exactly as entered (control characters and bidirectional overrides are rejected). Clients must render it as text, never as HTML.
