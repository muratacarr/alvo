# ADR 0006: Safe content import (ADD_NEW_ONLY) and export

Status: Accepted (slice 1D)

## Context
Users will ask an AI to produce learning content as JSON and upload it, repeatedly, into projects that already hold their own edited answers and history. The upload is untrusted input and the operation must be safe to repeat and to run concurrently.

## Decision
1. **Only additions.** The default and only strategy is `ADD_NEW_ONLY`: existing modules, topics, items, customised answers, attempts and review state are never changed. Replace and field-level merge are out of the MVP.
2. **Duplicate identity, in this order:**
   1. `externalId`, unique within the target project (never across projects or users);
   2. a fingerprint of item type plus the NFKC-normalised, case-folded, whitespace-collapsed prompt, enforced by `UNIQUE(project_id, fingerprint)` in PostgreSQL;
   3. a looser key (also ignores accents and punctuation) only **flags** a near-duplicate as `ambiguous`; it is skipped unless the caller passes `ambiguous=add`.
   Archived items keep their identity, so an import never resurrects them. Repeats inside the file keep the first occurrence.
3. **Preview writes nothing.** `preview` parses, plans and reports counts, samples, ambiguous and invalid entries. `commit` re-parses and re-plans inside its own transaction; it does not trust a previous preview.
4. **Atomic and idempotent.** One transaction. `Idempotency-Key` plus the canonical digest of the document is stored in `import_jobs` with `UNIQUE(project_id, idempotency_key)`: same key and document replays the stored result, same key with a different document is a `409`. Jobs store counts and a digest, never content.
5. **Concurrency.** A PostgreSQL advisory lock per project serialises imports (so "find or create module/topic" cannot race); items are inserted with `ON CONFLICT DO NOTHING` and counted via `RETURNING`, so a concurrent manual create can never be overwritten or duplicated.
6. **Hostile input.** Body cap (2 MiB, import routes only, counted on the stream), at most 2000 items, 100 modules and 200 topics per module, repeated JSON keys rejected, `NaN`/`Infinity` rejected, pathological nesting rejected without crashing, unknown fields rejected (identifiers, ownership and review state cannot be smuggled in), control and bidirectional-override characters rejected, a 15 s statement timeout, and a per-user commit limit (default 30 per hour).
7. **Per-item tolerance.** A bad item is listed (path and reason codes only, never the values) without hiding the rest. `commit` refuses a file with any invalid item, so what the user fixed is what gets imported.
8. **Ownership.** The target project comes from the URL and is checked first; the document can never name a user or project.
9. **Export is content only**, in the same schema, deterministic, without identifiers, ownership, timestamps or archived content, with a fixed download file name and `Cache-Control: no-store`.
10. **Module boundary.** `imports` parses, plans and records jobs; the `content` module owns all writes to its tables (enforced by an import-linter contract).

## Consequences
- Manual creation in the content API shares the same uniqueness rule: the same type and prompt in one project is a `409 duplicate`, even if the first one is archived.
- Migration `0005` back-fills fingerprints with a frozen copy of the rules; a test keeps that copy equal to the domain functions. A database that already holds duplicate items must be cleaned before upgrading.
- Preview and the rate limit for previews rely on the body cap; a general request rate limiter is still to be added before public exposure (slice 1F).
