# ALVO — CLAUDE CODE MASTER PROJECT SPECIFICATION

**Version:** 1.4 — Alvo naming; GitHub Actions chosen; public-repository secret hygiene, identity feasibility, paid API budget protection, Raspberry Pi 5 deployment, and secure CI/CD  
**Purpose:** Build Alvo: a secure, extensible, multi-user, goal-based learning and practice platform, initially focused on English communication, HR interviews and backend technical interviews, using a pragmatic modular monolith.  
**Operating mode:** Phase-gated, test-driven, security-first. **Do not implement the entire application in one run.**

---

## 0. Instructions to Claude Code (read first)

You are the project's principal software architect, senior full-stack engineer, test engineer, and application security reviewer. Work with the user **in Turkish**, but write code, identifiers, API specifications, tests, commit messages, architecture documents, and technical documentation **in English**.

1. **First response: planning only.** Inspect the repository and environment; propose the implementation plan, decisions, repository structure, threat model, phase/subphase backlog, and acceptance criteria. **Do not write application code until the user approves Phase 0 and explicitly authorizes the first implementation slice.**
2. Work in small vertical slices. After every subphase: demonstrate functionality, report tests, security review, trade-offs, remaining work, and **stop for user approval**. Do not automatically proceed.
3. Apply **test-driven development (Red → Green → Refactor)** to all application features and bug fixes. Show evidence of the sequence. Include security tests and authorization-negative tests.
4. Treat **security as a non-negotiable acceptance gate**. Security Reviewer must review **every change**, not only releases or high-risk changes. Findings block completion based on severity; critical/high issues cannot be deferred.
5. Follow SOLID, cohesion, clear module boundaries, dependency inversion, and maintainable code. Adopt design patterns **only where demonstrably useful**; justify each pattern. Avoid speculative abstractions and unnecessary infrastructure.
6. Maintain an **architecture decision record (ADR)** for consequential decisions and a concise decision/assumption log. If an external standard is referenced, check its **current stable official version** where access is available. Never claim conformance without evidence.
7. Choose secure defaults, minimize third-party dependencies and privileges, and never invent successful tests, scans, or external validation.
8. If a tool, dependency, provider, or credential is unavailable, explain the limitation and offer a secure test double or local substitute. Never silently weaken security.
9. Keep scope tightly MVP-sized: modular monolith, one deployable backend, one responsive PWA frontend, one PostgreSQL database. No microservices, Kubernetes, event sourcing, distributed messaging, or generic plugin frameworks unless a measured requirement emerges.
10. **Assume the repository will be public from day one.** Do not create or expose production secrets. Never commit `.env`, tokens, audio recordings, personal content, credentials, or generated sensitive reports. Apply the mandatory Public Repository & Secrets Policy below to migrations, fixtures, workflows, deployment manifests, tests, and documentation.


## 0A. Confirmed product and delivery decisions (authoritative)

- **Final product name:** Alvo. Public-facing product name, default repository name (`alvo`), Python package name (`alvo`) and Docker Compose project name (`alvo`). Do not retain the former Ape Speak / Ape Fluent names in newly generated artifacts.
- **Brand naming convention:** `Alvo` only, not `Alvo Learn` or `Alvo Estudo`.
- **Source hosting and CI/CD:** GitHub repository, potentially public, and **GitHub Actions** (not Jenkins). Use GitHub-hosted CI runners and GHCR where suitable.
- **Production target:** one Raspberry Pi 5 (16 GB) running Ubuntu Server ARM64, with Docker Compose, PostgreSQL and a securely published HTTPS PWA/API. The public ingress choice (e.g. Cloudflare Tunnel), SSD durability, backups and DNS must be validated in Phase 0.
- **Deployment policy:** build/test/scan automatically; deployment to production must require explicit operator approval. Prefer a pull-based release from the Raspberry Pi of approved immutable image digests; avoid CI holding production root credentials.
- **Identity requirement:** the product owner prefers **ChatGPT-only sign-in**, but this must be technically and contractually verified for a third-party hosted PWA prior to implementation. Login does NOT by itself grant delegated ChatGPT AI access or paid OpenAI API usage. If official eligibility is unavailable, report a blocking product decision; do not implement unsupported auth methods or insecure workarounds.
- **Free-first speech:** browser speech features where supported and disclosed; optional local/on-device STT later. Never silently fall back to an application-funded OpenAI API call.
- **Paid speech:** owner-funded OpenAI STT/TTS available only to individually approved users after server-side authorization, explicit intent, budgets, quota reservation and a global kill switch. The subscription to ChatGPT does not pay these API bills. Whisper is STT, not TTS.
- **Security gate:** apply public-repository secret discipline to all source, migrations, CI/CD, images and operations. Apply automatic security review after **every change**.
- **Scope:** secure modular monolith, SOLID with pragmatic patterns, TDD, phased approval checkpoints. No premature microservices or Kubernetes.

## 0B. Mandatory Public Repository & Secrets Policy (P0 security requirement)

**Threat model:** The GitHub repository, every commit and Git history, CI logs, container images, release artifacts, test fixtures, and documentation may become publicly accessible. Treat repository contents as public. `.gitignore` is a guardrail, not a secret-management system.

### Allowed vs prohibited content

- **Never commit:** real or realistic functioning API tokens; provider OAuth client secrets; OpenAI API keys; database passwords or production connection strings containing credentials; signing/encryption keys; SSH private keys; tunnel tokens; registry credentials; access/refresh tokens; cookies; session secrets; production `.env` files; backup decryption keys; user PII; private recordings; real account identifiers; production dumps; secret-containing CI logs or artifacts.
- **Migration code is not configuration storage.** Alembic revisions must NEVER embed passwords, API keys, encryption material, real seed users, authentication tokens, or host-specific private endpoints. Migrations may add columns, constraints and deterministic non-sensitive reference rows only when necessary and reviewed. A migration that needs access to an external service or production secret is architecturally suspect and requires separate review; keep secret retrieval out of the migration source.
- **Seed/demo/fixture data:** synthetic, deterministic, obviously fake and non-credential-bearing. No production exports, copied personal user answers, real email addresses, reused passwords or provider secrets. Test credentials only through isolated test settings with conspicuously invalid placeholders, never shared with staging/production.
- **Permitted to commit:** `.env.example` and config templates containing placeholder identifiers ONLY (e.g. `CHANGE_ME`, `YOUR_CLIENT_ID`) and non-sensitive names; publicly safe sample JSON/schema, migration scripts without secrets, Docker Compose templates referencing external secrets, operational documentation without credentials. No defaults that silently turn placeholders into production-accepted secrets.
- Keep sensitive files out of Git (`.env`, `.env.*` except explicit examples, `secrets/`, `*.pem`, `*.key`, `*.p12`, database dumps, backup archives, local state, recordings); do not rely on patterns alone. Never print environment variables wholesale or enable shell debugging around credential-bearing commands.
- Development, CI and production use isolated identities, least-privilege permissions and separate credentials. On the Raspberry Pi inject production secrets **at runtime** from root-/service-owned permission-restricted files or suitable secret management, outside the checkout and Docker build context. Docker Compose may reference `secrets:` files, but the real file paths and values must remain private. Never use Dockerfile `ARG`, `ENV`, image layers, build output, frontend `VITE_*` config, baked assets, or CI artifacts to transport server credentials.
- Authentication/OIDC: public client IDs and issuer URLs are not inherently secrets, but client secrets, tokens, PKCE verifier, session material, and signing keys are sensitive. Distinguish public metadata from credentials. Never commit real environment-specific identifiers if they reveal private infrastructure unnecessarily.

### Mandatory preventative controls

1. **Pre-commit:** run a maintained secret scanner (e.g. Gitleaks) on staged changes with a narrowly scoped reviewed configuration; add lightweight protected-file checks. Do not bypass findings casually or hide them with blanket allowlists.
2. **CI / pull requests:** scan the entire relevant commit range (including history where feasible), files, examples, workflows and dependency artifacts for secrets; fail CI for actionable findings. Test migrations/fixtures specifically for embedded credentials; run workflow security analysis and prevent untrusted PR jobs from reading sensitive secrets.
3. **GitHub settings:** enable GitHub secret scanning / push protection where available on the selected repository plan; document coverage limitations and keep independent scanners. Protect main, require status checks, restrict Actions permissions, pin trusted actions to reviewed full-length SHAs, and require approval for production deployment.
4. **Runtime:** fail at startup when required secrets are absent, placeholder-valued, malformed or dangerously weak. Do not create or log fallback production credentials. Use documented rotation for DB, OAuth, OpenAI, tunnel and signing material. Never expose secrets in exception messages, health endpoints, error responses or telemetry.
5. **Review every database migration and deployment change** for confidentiality, tenant isolation, accidental data export, destructive operations, unsafe shell interpolation and leaked parameters. No SQL statements that log sensitive parameters unnecessarily. Migration tests must run on disposable synthetic data.
6. **Public-release gate:** audit tracked files, sample files, full commit history as feasible, gitignore rules, build contexts, image layers, CI logs and generated docs before repository publication. If any credential is leaked, **revoke/rotate it immediately**, investigate access, scrub public exposure/history with an approved procedure where appropriate, and document the incident. Removing a secret in a later commit does not make the leak safe.
7. Keep a sanitized `docs/security/public-repo-checklist.md` and `docs/ops/secrets-management.md` with setup and rotation instructions, not values. Never place sensitive security review findings containing exploitable private deployment details into the public repository; use a private reporting channel and commit only sanitized summaries.

### Required security tests and acceptance criteria

- Seed and migration scanners flag realistic embedded credential strings; migration scripts contain zero real secrets or personal data.
- `.env.example` alone must NOT make the production application boot with working credentials; the startup validator rejects placeholders.
- Tests prove that no backend OpenAI key, database secret, session credential or tunnel token reaches JS bundles, HTTP error bodies, container image layers, logged commands, or CI artifacts.
- Untrusted fork PRs have **zero access** to production secrets or production deploy credentials.
- Secret detection failures block merge/release, and a documented leak-response drill explains revocation/rotation and history remediation.

## 1. Vision and product boundaries

**Alvo** is a **general-purpose, goal-oriented, project-based learning and practice platform**, not just an HR interview question app. It helps learners prepare for HR interviews, technical backend interviews, common English patterns, workplace conversations, and custom topics. It provides structured practice and spaced repetition to progress from supported exercises to unscripted English responses.

### MVP user journeys

1. Sign in and sign out with **Sign in with ChatGPT**, if the necessary official provider access, terms and supported web integration have been verified. No local email/password registration in the target product. See identity feasibility gate below; do not fake OAuth or use unofficial session extraction.
2. Create and manage **private projects**, e.g. `HR Interview`, `Backend Technical Interview`, `English Patterns`.
3. Organize content as **Project → Module → Topic → Learning Item**. Learning item types: `question`, `phrase`, `vocabulary`, `concept`, `scenario`. Start with `question` fully supported, structure other types for incremental extension without breaking contracts.
4. Add/edit/archive learning items manually.
5. Download a versioned JSON template; ask ChatGPT or another AI to produce content using it; upload JSON **to an existing project** or to a new one.
6. **Existing questions must survive subsequent imports.** Add new items, skip exact duplicates, review ambiguous items, preserve user-customized answers and all learning history.
7. Practice reading, listening (TTS), writing, and graduated speaking exercises; store progress and schedule reviews.
8. Use a daily dashboard with recommended new material, due reviews, and transparent progress. Default to unlimited new items and reviews unless the user configures limits.
9. Export project content as versioned JSON without inadvertently exporting credentials, practice recordings, or sensitive account data.
10. Use the app on desktop and phone as a **responsive installable PWA**. The system should remain functional in supported online mode; offline learning is an optional later milestone, not an unverified MVP promise.

### Progressive speaking methods

- `read_aloud`: read sample answer aloud.
- `shadowing`: listen and repeat (can begin with simple TTS playback).
- `fill_gaps`: selectively hide phrases from the sample answer; reveal/check correct answers; favor spoken completion once STT exists.
- `keyword_speaking`: hide full text and show key prompts such as `Experience`, `Technologies`, `What I enjoy`, `Career goal`.
- `guided_speaking`: show response outline without scripted answer.
- `free_speaking`: show question alone and record response.
- `follow_up_challenge`: ask fresh HR or technical follow-up questions (later AI phase).

**MVP implementation priority:** `read_aloud`, `fill_gaps` (initially text-check + verbal practice instructions), `keyword_speaking`, `free_speaking` with browser recording as available; add advanced shadowing, automatic transcription, and adaptive follow-up later. Never represent typed fill-gap answers as verified spoken responses. Show graceful fallback when microphone permissions or browser APIs are unavailable.

**Learning principle:** Read → Understand → Recall → Produce → Evaluate → Repeat. Do not optimize for rote memorization of a single answer. Allow alternate correct phrasings, and keep **English language quality** separate from **technical-content accuracy** when automated evaluation is introduced.

### Out of scope for initial MVP

Social/sharing/team projects; payment; native iOS/Android; full offline synchronization; real-time conversational voice AI; vector databases; AI scoring presented as objective truth; advanced analytics; multiple organizations; heavy asynchronous job infrastructure. Keep safe extension seams for future needs without implementing these features now.

## 2. Technology baseline (confirm during Phase 0)

- **Frontend:** React + TypeScript + Vite, Tailwind CSS; accessible responsive UI; PWA installability; React Router and a lightweight server-state/data-fetching approach as warranted.
- **Backend:** Python + FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic; strict typing.
- **Database:** PostgreSQL.
- **Development tooling:** Docker Compose for local services; pinned, actively maintained dependencies, reproducible lockfiles; CI for format, lint, type checking, tests, dependency auditing, secret scanning, and security gates.
- **Testing:** pytest (backend), suitable modern TypeScript test runner + React Testing Library (frontend), Playwright for critical end-to-end user journeys.
- **Audio:** default to browser speech synthesis/recognition when supported; treat browser recognition as potentially remote-processed, never promise it is private/offline. Browser MediaRecorder with feature detection, explicit consent and bounded size/duration; optional on-device Whisper later; paid OpenAI speech is opt-in, admin-entitlement gated, quota guarded and disabled by default. No implicit paid fallback.
- **FSRS:** use a maintained implementation or an isolated scheduler adapter with documented algorithm/version and deterministic tests; track item-specific due dates, review ratings, and history. Do not equate FSRS recall prediction with speaking skill proficiency.
- **Deployment:** Raspberry Pi 5 (16 GB), Ubuntu Server 64-bit ARM64, Docker Engine + Compose, single FastAPI application + built React PWA + local PostgreSQL private service; securely managed public ingress, TLS, backups, observability, and controlled GitHub Actions CI/CD. No public database exposure. See the mandatory self-hosting section.

Choose supported stable releases at implementation time; record decisions and dependency versions. Avoid adding React state libraries or background queues by default.

## 3. Architecture: pragmatic modular monolith

A **single FastAPI application** organized by business capabilities, not a monolithic `services.py` and not microservices disguised as Python packages.

Proposed backend modules:

- `identity`: verified OpenAI identity integration (subject to eligibility), local app session management, account linking policies, auth policies.
- `projects`: project ownership and lifecycle.
- `content`: modules, topics, learning items, answer examples, keywords, translations, item versioning.
- `imports`: template schema, validation, preview, deduplication, import execution and audit.
- `practice`: practice sessions, attempts, typed answers, audio metadata and recording lifecycle.
- `review`: FSRS scheduling, review state and history.
- `progress`: per-skill progress and user dashboard read models.

Shared foundation limited to configuration, database transactions, security primitives, error contracts, observability, and truly cross-cutting utilities. **No catch-all shared business module.**

Within a module, separate when beneficial:
- `api` / transport contracts and request validation;
- `application` / explicit use cases and orchestration;
- `domain` / business invariants and policies;
- `infrastructure` / SQLAlchemy persistence, filesystem/object storage adapters, external providers.

Enforce dependencies toward the domain: routes are thin, domain entities are not ORM models, infrastructure does not define business policy, Pydantic request/response models are not persistence entities. Prefer composition, protocols/interfaces at real boundaries, and explicit transactions. Avoid generic repository scaffolding for every table; add repositories when they protect business logic or clarify testing. No gratuitous Unit of Work abstraction if SQLAlchemy's transaction boundary is already adequate. Use Strategy for clearly varying practice modes or import policies; Adapter for STT/TTS/LLM; Factory only for non-trivial construction. Document WHY patterns exist.

Suggested repository layout (adapt if existing repo dictates):

```text
apps/
  web/
  api/
    src/ape_speak/
      identity/
      projects/
      content/
      imports/
      practice/
      review/
      progress/
      shared/
    tests/
packages/
  contracts/                 # Only if genuine shared generated contracts are justified
docs/
  architecture/
  adr/
  security/
  api/
  decisions/
.github/workflows/
compose.yaml
README.md
```

Explicit module ownership and APIs are mandatory. Avoid arbitrary direct cross-module database writes. Keep database schema constraints as a second line of defense. Use Alembic migrations with reversible plans wherever practical. Migrations must contain schema changes and safe non-sensitive data transformations only—never embedded secrets, environment credentials, API keys, or real user records.

## 4. Identity, authorization and multi-user isolation

### Required

- **Product identity requirement: ChatGPT-only sign-in.** Verify access to the official Sign in with ChatGPT identity flow for this exact hosted PWA, registration/onboarding requirements, provider eligibility and authorized scopes **before implementation**. If unavailable, report a **blocking feasibility issue** and propose user-approved options; do not silently fall back to passwords or substitute "Sign in with Google". Test-only synthetic identities are permitted solely in isolated environments and may not expose production routes.
- Use standards-compliant OAuth/OIDC semantics where supported: authorization code + PKCE, state/nonce as applicable, exact redirect URI allowlist, issuer/audience/signature/time validation according to the official flow, unique stable provider subject for identity mapping, explicit consent and secure token handling. Never ask for ChatGPT credentials or scrape browser cookies.
- **Identity is not usage entitlement.** ChatGPT sign-in does not imply that a user's subscription may fund the application's AI requests. Delegated subscription/usage features require separately supported provider authorization, terms, and explicit consent. Do not claim universal support or silently bill the user's plan. If unsupported, disable those AI routes and report the blocker.
- Account lifecycle: create an internal user on verified provider identity; support secure logout, identity unlink/deletion and local data handling within provider constraints. Email is not a substitute for provider subject; do not expose another account's projects during linking.
- If sign-in is not yet authorized during development, implement identity behind an explicit verified-provider integration boundary and use only non-production mock adapters in tests; do not ship an authentication bypass.
- Prefer **server-side opaque sessions** in `HttpOnly`, `Secure`, appropriately scoped `SameSite` cookies. Implement idle/absolute expiration, rotation after sign-in and sensitive changes, revocation on logout/reset, and CSRF protection for state-changing cookie-authenticated requests. Do not store bearer tokens in localStorage.
- Document session storage and revocation implementation compatible with a modular monolith and selected deployment.
- Enforce **deny-by-default object authorization** on the server for **every** project, module, topic, item, import, practice, audio, export, and review read/write. Clients never choose an authoritative `user_id`. No IDOR / BOLA / cross-tenant disclosure.
- Scope queries by current principal and authorized project; validate parent-child ownership (including nested/moved records) and disallow inconsistent references. Avoid leaking account or object existence through error messages or timing where practical.
- Include ownership isolation tests with **two different users** for every relevant endpoint, including nested resources, import previews/commits, exports, and recording downloads.
- Prepare a defensible account deletion and data retention policy, and avoid retaining raw audio longer than necessary.

### API hardening

- TLS in production, secure reverse-proxy and trusted-host configuration; CORS allowlist only, no wildcard with credentials.
- CSRF protection, secure headers including CSP appropriate for Vite build, HSTS at HTTPS edge, sensible Referrer-Policy, no sensitive caching.
- Strict Pydantic boundary validation; whitelist writable properties to prevent mass assignment; output schemas with minimal fields; bounded pagination and filters; UUIDs or non-enumerable IDs **do not replace authorization**.
- Per-endpoint authorization, request body size/timeout limits, query complexity/pagination bounds, rate limits on login, registration, reset, exports/imports and expensive operations. Rate-limiter semantics must be correct for the deployment topology (do not rely on per-process memory in scaled deployments).
- Consistent safe error formats, request correlation IDs, secret/PII redaction in logs, security audit events, and no stack traces/SQL errors in responses.
- Parameterized SQL/ORM, no unsafe dynamic SQL; protect against stored/reflected XSS, injection in rich content, SSRF for future URL-import/AI features, path traversal, unsafe deserialization and file-upload attacks.
- Model threat boundaries for untrusted AI-generated content and prompt injection if/when LLM features are added; imported instructions are always **data**, never executable/system instructions.

## 5. Security baseline and quality gate

Use these authoritative references (verify the current stable version when internet access is available):

- **OWASP ASVS 5.0.0** as the web/application security control baseline, with an evidence-backed, risk-appropriate **Level 2 target** for applicable controls; document applicable IDs and justified exceptions. Do not claim formal ASVS certification.
- **OWASP API Security Top 10 (2023)** for API-specific threat review, particularly broken object-level and function-level authorization, unrestricted resource consumption, and unsafe API consumption.
- **OWASP Top 10** current official stable release at build time; **OWASP Cheat Sheet Series** for sessions, authentication, CSRF, file upload and logging.
- **NIST SP 800-63B-4** for applicable authentication practices.
- Use secure-by-design principles: least privilege, fail closed, defense in depth, minimized attack surface, documented secrets/data handling.

### Mandatory Security Reviewer on EVERY change

Create a reusable repository-level security-review workflow (`docs/security/review-checklist.md` and optionally a Claude Code subagent definition if the local Claude Code environment supports it). For **each code, migration, configuration, dependency, or API change**, automatically execute a security review before saying the slice is done. Where a subagent is not available, perform the same checklist in the main workflow—never skip it.

Review scope (risk-proportional depth, not optional execution):
1. Changed trust boundaries and data flows.
2. Authentication/session/CSRF/CORS and authorization/BOLA/BFLA impacts.
3. Validation, injection, XSS, file handling, serialization and resource limits.
4. Secrets, privacy, logging and sensitive data retention.
5. Dependency vulnerability posture, SBOM/lockfile integrity, and supply chain impact.
6. Misconfiguration and infrastructure hardening.
7. Regression tests including malicious/negative cases and OWASP mapping.

Deliver a concise per-slice security report: files/scope reviewed, applicable controls, findings with severity and exploitability, tests/verification evidence, fixes and residual risks. **Critical and High block acceptance; Medium must be fixed before release or require explicitly documented owner-approved exception with compensating controls and expiry.** Never hide issues. Findings must be included in the Definition of Done.

## 6. JSON template, import, merge and export

### Versioned interchange contract

- Publish **JSON Schema** and a complete sample file in `/docs/api/` or an equivalent public-in-app location; offer in-app download.
- JSON top-level uses `schemaVersion` (e.g. `1.0`), optional descriptive project metadata, and `modules -> topics -> items`.
- Items have a `type`, required `prompt` (or equivalent well-documented type-specific content), optional `externalId` (unique **within target project/source namespace**), `sampleAnswer`, `translation`, `keywords`, `difficulty`, `tags`, `followUpQuestions`, and optional per-mode practice configuration. Make rules explicit for items that are phrases/vocabulary rather than questions.
- Validate with JSON Schema at boundary and Pydantic domain mapping. Explicitly handle missing/unknown versions and fields, Unicode normalization, bounds and malformed payloads; no arbitrary code or markup execution.

### Safety and idempotency

- **Default import strategy: `ADD_NEW_ONLY`**. Existing project/module/topic/item records, user-customized sample answers, recordings, learning attempts, FSRS states, and progress must remain unchanged.
- Import to an **existing user-owned project**, or create a new project explicitly. Never infer a user from JSON.
- Preview before commit: counts and samples of new items, exact duplicates, ambiguous near-duplicates, invalid entries, and created modules/topics; clear resolution UI. No writes during preview.
- Duplicate policy: (1) stable `externalId` in an explicitly defined namespace, (2) normalized canonical prompt + item type within the target project (define normalization and scope precisely), (3) semantically similar content is **flagged, never silently merged**. Preserve distinct legitimate items across topics and languages according to documented rules.
- Build stable content fingerprints. Enforce relevant **database uniqueness constraints**, not only in-memory checks; support safe retries and simultaneous imports. Use transaction boundaries and idempotency keys or deterministic equivalent for commit; race tests required.
- Keep import execution **atomic** for MVP; on any unhandled/validation error rollback and preserve prior data. Set safe caps on bytes, depth, total entries, field lengths and processing time to avoid resource exhaustion. Defend against duplicate JSON keys and pathological nesting according to parser capabilities.
- `SMART_MERGE` (manual field-level approval) is later; destructive replace is explicitly **out of MVP**, unless safely designed with backup and separate confirmation.
- Maintain `import_jobs` with owner, project, source digest, counts, status, error summary and timestamps. Avoid recording raw secrets/PII or entire user JSON in logs.
- Export project **content only** by default, deterministic and schema-valid; no passwords, session tokens, private audio, answers authored as personal journal content unless explicitly selected, or accidental cross-user data.

### Illustrative v1 JSON (refine and formalize in Phase 0)

```json
{
  "schemaVersion": "1.0",
  "program": {
    "title": "Backend Developer Interview",
    "targetLanguage": "en",
    "level": "B1",
    "modules": [
      {
        "title": "Technical Interview",
        "topics": [
          {
            "title": "Dependency Injection",
            "items": [
              {
                "externalId": "backend-di-001",
                "type": "question",
                "prompt": "What is dependency injection?",
                "sampleAnswer": "Dependency injection reduces coupling and improves testability.",
                "translation": "Bağımlılık enjeksiyonu nedir?",
                "keywords": ["coupling", "testability", "dependencies"],
                "tags": ["backend", "design-patterns"],
                "followUpQuestions": ["How does dependency injection help unit testing?"],
                "practice": {
                  "modes": ["read_aloud", "fill_gaps", "keyword_speaking", "free_speaking"]
                }
              }
            ]
          }
        ]
      }
    ]
  }
}
```

The uploaded JSON template is **not** a database snapshot. Never import IDs, authentication state, review history or ownership claims from it.

## 7. Practice, audio, learning and evaluation

- Reading: show prompt, answer, translations/keywords with reveal controls.
- Listening: browser TTS where available, configurable playback rate, language and voice; fallback to text when unavailable. Do not promise identical voices across platforms.
- Writing: save user response and allow self-correction; preserve prior attempts.
- Speaking: start/stop recording with explicit permission, visual recording state, duration and size limits, cleanup and deletion; store recordings privately or use local-only temporary audio until server storage is justified. No auto-upload without clear user action/notice.
- Gaps: support reproducible fill-gap generation and an author-defined version; preserve acceptable alternatives where feasible. Typed correctness is **not** a speech score.
- Keyword/guided/free mode: reveal progressively less information; a user can skip ahead or request help.
- FSRS: only schedule reviews from real review ratings, include due/new queues and historical reviews, and keep learning history stable across reimports and content edits. Make review resets an explicit separately confirmed action.
- Future automated assessment separates: recall, fluency, grammar, vocabulary, relevance, technical accuracy. STT output alone cannot reliably measure pronunciation; show uncertainty and avoid fabricated scores.
- Ensure accessible interaction: keyboard navigation, labels, visible focus, transcripts/captions or equivalent text, reduced-motion preference, and WCAG 2.2 AA as a **design target** with testing evidence (no unsupported compliance claim).

## 8. Data modeling and privacy rules

At minimum: `users`, `sessions` (or documented secure session store), `projects`, `modules`, `topics`, `learning_items`, `practice_attempts`, `review_states`, `review_events`, `import_jobs`. Add `audio_assets` only if durable storage is approved. Consider `learning_item_versions` if content editing would otherwise corrupt history.

- Every project has a single owner in MVP. Parent-child foreign keys and database constraints guard integrity.
- Represent deletes through safe archive/soft-delete where preserving history matters; document eventual deletion and retention rules.
- Project isolation must be testable at the storage/repository/use-case/API layers. Do not rely only on opaque identifiers.
- Minimize personal data and log metadata rather than contents. Specify data deletion paths, backup restoration boundaries, recording retention and encryption at rest/in transit depending on chosen environment.
- Define stable schema migration rules. No destructive migration without tested rollback/backups.

## 9. API contracts, reliability and operations

- Version APIs (`/api/v1`); OpenAPI must match real error and success behavior.
- Use explicit request/response DTOs and predictable HTTP status codes; no leaking SQLAlchemy internals.
- Support page-sized collections, stable ordering and bounded pagination.
- Ensure duplicate import concurrency is safe with DB constraints, transaction isolation, and integration tests.
- Have health/readiness checks without disclosing internals, structured redacted logs, correlation IDs, and basic metrics; alerts can wait until deployment phase.
- Separate development/test/production configuration; validate settings at startup, secure secret injection, restricted DB roles, backed-up database and migration rehearsal.
- Add a minimal local runbook, seed/demo content without personal data, and a production hardening checklist.


## 9A. Speech and AI provider strategy — free-first, explicit authorization

**NON-NEGOTIABLE BUSINESS INVARIANT:** The application must not consume the owner's paid OpenAI API balance unless *all* server-side entitlement, user intent, quota, cost-reservation, global-budget and provider-availability gates pass. Provider SDK calls must have one centralized guarded entry point; direct SDK use from routes, job workers, or frontend is prohibited.

### Provider choices

1. **Default, no app API spend:** browser `speechSynthesis` for TTS; browser `SpeechRecognition` only after capability detection and an explicit disclosure that implementation may transmit audio to the browser vendor and may be unavailable. No claim of universal device/offline support. Support manually typed answers when recognition fails.
2. **Optional locally executed STT:** self-hosted or on-device open-source Whisper where hardware/deployment supports it; OpenAI API charge is zero but computing, latency, distribution, memory and hosting are **not** free. Defer if too costly to ship in MVP. Local TTS is a separate capability, not Whisper.
3. **Paid OpenAI Speech API:** admin-approved users only, disabled by default, separate STT and TTS entitlements and granular caps. Speech requests spend the application's API project balance, **not** the user's ChatGPT subscription. Obtain user consent when audio/text leaves the device, and display when the paid provider will be used.
4. **Delegated ChatGPT LLM usage:** independently check official support and eligibility for hosted web applications; never convert a ChatGPT login token into a standard API credential, and never route provider-delegated subscription requests through unsupported backend proxies. No scraping, cookie extraction, subscription sharing hacks, or silent API-funded LLM fallback. If no eligible integration, LLM features are unavailable until officially supported/approved.
5. **No silent escalation:** a browser/local failure must produce a clear free fallback, typed input or user-visible error; it must never automatically switch to a paid API. Allow the user to choose a paid option only if they have server-side entitlement.

### Boundaries and principles

- Separate `IIdentityProvider`, `ITextGenerationProvider`, `ISpeechToTextProvider`, `ITextToSpeechProvider`, and `IPaidUsageAuthorizer` **only when implementing the corresponding feature**. Do not build a speculative multi-provider framework. Paid provider adapters must depend on a dedicated centralized `BudgetGuard` and auditable usage ledger.
- Provider configuration and administrator approvals are **server-side**, least-privileged; no exposed OpenAI key, no client-controlled model/provider/pricing metadata, no bypass via alternate endpoint, web socket or background task. Application-level authorization and project ownership precede any paid request.
- AI-produced text/JSON and speech transcriptions are untrusted data and must not be promoted to system instructions or database/admin actions. Never include tenant secrets or unrelated user data in provider prompts.

## 9B. Mandatory paid API spending protection — defense in depth

Design the controls **before any paid integration**; make actual paid provider calls a separate, explicitly approved implementation slice. The cost controls are security controls and release blockers, not optional analytics.

### Layer 1 — OpenAI account/project safety

- Use a **dedicated OpenAI API project** and a restricted, server-side credential for Alvo; never use an organization-wide key with unnecessary permissions. Do not reuse development keys in production.
- Configure the provider's **project hard spend limit** where supported, and optionally an **organization-level hard spend limit** as a backstop; enable `Enforce a hard limit`, not just budget alerts. Configure early spend alerts (e.g. 50%, 75%, 90%). Restrict enabled models and model-specific rates to those actually required. Verify controls in the live account manually with redacted evidence, never claim configuration was applied without proof.
- Hard spend limit enforcement may be **delayed**, so the actual external bill can exceed the provider limit slightly. The app's own cap must be below the provider's hard cap with an operational safety margin; do **not** promise an absolute external billing guarantee. Alerts alone are not limits.
- Keep prepaid auto-recharge disabled or tightly bounded according to administrator choice, with independently verified provider billing settings. Do not programmatically change billing caps, buy credits, or enable additional models without explicit owner approval.

### Layer 2 — default-deny paid feature entitlement

- `paid_stt_enabled=false`, `paid_tts_enabled=false`, `paid_llm_enabled=false` by default, at user level AND globally. User role or successful ChatGPT authentication alone never grants paid usage.
- Only a designated admin can grant individual per-feature entitlements; change grants and limits in audited admin operations protected by stronger authentication/re-authentication as available. No client-side entitlement flags accepted as authority.
- Require a recorded, current user-initiated operation and processing consent; block scheduled/background paid actions unless separately, explicitly authorized. No anonymous paid calls.

### Layer 3 — enforce quotas and worst-case preflight limits

- Per user: calls/minute and calls/day, parallel request cap, daily and monthly USD budgets, monthly STT duration, monthly TTS character count, per-audio length/bytes, per-text size, and optional per-feature limits. Global: concurrent paid jobs, calls/minute, daily/monthly estimated USD budgets, and emergency off switch. Configure all limits server-side, use secure conservative defaults, and allow reductions without redeployment.
- Before every paid call, enforce auth/session, tenant/project ownership, admin entitlement, per-feature policy, content-type/magic-byte verification when practical, request size, validated length/duration, bounded model/options, per-user and global budgets, rate and concurrency caps, and explicit user intent.
- Never rely on a `Content-Length` header or client-reported recording duration as authoritative. Enforce request-body streaming limits, inspect actual received bytes, verify media characteristics server-side when needed, and reject overlong/malformed audio **before** provider upload. Bound TTS character/token count and provider output size; forbid client-selected arbitrary premium models or expensive modes.
- Maintain a server-owned versioned **pricing catalog** from official prices. Forecast conservatively (include potential output and rounding) and **fail closed** if model price is missing/stale or maximum cost cannot be bounded. Don't invent current prices. For LLM generation, enforce server maximum input/output tokens and estimates if an authorized paid LLM mode is ever added.

### Layer 4 — atomic reservation, accounting and abuse-resistant concurrency

- All paid calls go through `authorize → estimate worst-case spend → atomically reserve funds/quota → call provider → reconcile actual usage → release unused reserve`. Reserve against **available balance = limit − committed usage − outstanding reservations** for both user and global scopes.
- Implement reservation in a DB transaction using row locks / conditional updates; test simultaneous requests so N parallel calls cannot each spend the last available allowance. Give each operation an idempotency key, bounded TTL and unique constraint; never permit retries or duplicate webhooks to double charge or double consume reservation.
- Record status transitions (`reserved`, `sent`, `settled`, `failed`, `uncertain`, `cancelled`) and retain a minimal auditable ledger including user ID, request ID, provider, selected model, usage quantity, estimated cost, settled cost, time, policy decision and sanitized error code. Never log raw audio, full prompts, tokens, or API credentials by default.
- On timeout or uncertain provider response, **do not blindly release** reserved funds and retry; external work may have been billed. Keep an `uncertain` state, bound retries, reconcile provider usage where feasible and fail closed until reconciliation or safe expiry policy. Track divergence from provider billing. Avoid auto-resubmitting expensive jobs.
- For MVP, prefer PostgreSQL transactional safeguards over a distributed queue or Redis unless measurements justify them. Ensure one guarded provider gateway; enforce cost protections on synchronous and future asynchronous paths alike.

### Layer 5 — kill switch, monitoring, graceful failure

- Administrator-controlled `PAID_AI_ENABLED=false` global kill switch and per-provider/per-feature circuit breakers; shutdown must prevent new reservations and new outbound paid calls across all API instances (persist configuration centrally, not only process memory). Test emergency shutdown during concurrent work.
- Fail **closed** when quota store, pricing rules, admin entitlement, usage ledger, or budget service is unavailable. No bypass mode, no fallback to a different paid model or API project.
- Surface clear error codes: `PAID_FEATURE_DISABLED`, `PAID_ACCESS_DENIED`, `USER_QUOTA_EXCEEDED`, `GLOBAL_BUDGET_EXCEEDED`, `BUDGET_GUARD_UNAVAILABLE`, `PROVIDER_LIMIT_REACHED`; avoid revealing private financial values. Continue to allow free practice and preserve user data.
- Monitor attempted-denied requests, outstanding/uncertain reservations, settled usage, cost estimates vs provider reporting, per-user anomalies, spending velocity, authentication spikes, error rates and abuse patterns. Alert administrator before thresholds; retain minimal privacy-respecting audit events.
- Limit credentials and outbound network access to the backend paid gateway; do not send third-party API keys or access tokens in telemetry, exceptions, or logs. Keep paid calls disabled by default in local development, test and CI; use mocked providers and explicit deliberate opt-in for any integration test that spends real funds.

### Minimum mandatory cost-security tests (Red → Green → Refactor)

1. Unauthenticated, unentitled, other-user, and revoked users cannot trigger a provider call; counters and charges remain zero.
2. At the exact user/global budget boundary, request is rejected **before** provider invocation; conservative estimate covers worst allowed duration/output.
3. 20 concurrent requests competing for the final allowance do not oversubscribe either user or global pool; assert ledger and calls.
4. Identical idempotency keys and retry storms never produce extra provider calls or duplicate settlements.
5. Provider timeout/partial failure creates a bounded, auditable uncertain reservation and never silently refunds a possibly billed call.
6. A malformed file, spoofed audio duration/MIME type, oversized stream, excessively long TTS input or unexpected model ID is rejected locally.
7. Global kill switch, revoked entitlement, missing/old price and unavailable DB/ledger cause **zero additional paid calls**.
8. Browser STT failure or local Whisper OOM does **not** auto-fallback to a paid provider.
9. Rate-limit, provider bill cap/429, insufficient credits, and transient failures show safe messaging without uncontrolled automatic retries.
10. Billing/account usage reconciliation and concurrent admin updates are tested with deterministic mocked records; tests never need a real API key.

**Release gate:** no paid adapter may be enabled in any environment until all cost-security tests pass, documented administrator entitlement is implemented, provider project hard spend limit is verified, kill switch is exercised, and the user expressly approves the spend-bearing slice.

### Required Phase 0 artifacts

Add `docs/security/ai-spend-threat-model.md`, `docs/architecture/speech-provider-decision.md`, `docs/security/api-spend-policy.md`, and ADRs as appropriate. Document abuse cases (stolen session, malicious authorized user, replay, concurrency race, broken price catalog, provider outage, admin account compromise, fake file durations), default limits with rationale, expected worst-case loss, residual provider billing overshoot, and rollback/incident plan. No fabricated pricing, guarantees or configuration proof.

## 10. Testing & release gates

**TDD for every feature:** first failing test, minimal passing implementation, refactor safely. Report what failed before implementation and what passed afterward.

Minimum test coverage includes:

- Unit: domain invariants, normalization/dedupe, FSRS schedule contracts, item types, import policy.
- Integration: FastAPI + real test PostgreSQL with migrations, transaction rollback, idempotent retry and concurrent import, schema-version rejection.
- Authorization: two-user access matrix for CRUD, imports, audio, export, progress, parent-child mismatch, and IDOR attempts.
- Security: auth abuse/rate limits, session fixation/rotation, CSRF, CORS, invalid mass assignment, overlarge/deep JSON, XSS rendering, unsafe filenames, invalid content types, sensitive logging.
- Frontend: mode transitions, form validation, progress, PWA mobile breakpoints, accessibility and denied microphone permission.
- E2E: registration/login, create project, import JSON, re-import same JSON (zero new), import overlapping JSON (only new), practice, review, logout, second user denied access.
- CI: formatter, linter, typing, tests, dependency scan, secret scanning, static security checks, container/dependency scanning when applicable. Document false positives rather than suppressing silently.

Coverage is a diagnostic, not a substitute for meaningful abuse and authorization tests. Always inspect failing/flaky tests; never mark a stage complete if its gates fail.

### Definition of Done — every subphase

- User-approved slice scope and acceptance criteria met.
- Red/Green/Refactor evidence and relevant tests passing.
- API contract/documentation and migrations updated.
- Security Reviewer run for **every change**, findings fixed or handled according to severity policy.
- Ownership and privacy implications reviewed; negative-path and regression tests supplied.
- No committed secrets, no undocumented critical design deviation, no unresolved critical/high risks.
- Clear user-facing demo steps; concise Turkish report listing changed files, tests/commands/results, security checks, trade-offs and next proposed slice.
- **Stop and request approval before the next slice.**

## 11. Milestones — phase-gated, not one-shot

### Phase 0 — Architecture and security design (**NO CODE**)

Deliver:
1. scope and prioritized functional/nonfunctional requirements;
2. proposed modular monolith repository layout and module contracts;
3. Mermaid context/container/module diagrams and key data relationships;
4. security threat model (assets, entry points, trust boundaries, likely attacks, controls, residual risks), security baseline control mapping;
5. ChatGPT-only sign-in feasibility evidence, authentication/session/CSRF architecture, separate ChatGPT usage authorization eligibility, and multi-user isolation policy;
6. versioned JSON import/merge invariants and rough API contracts;
7. technology choices with rationales/ADRs, and dependency check plan;
8. phased backlog with small subphases, TDD acceptance tests, risk/complexity notes;
9. assumptions/questions that actually block safe implementation;
10. provider-cost threat model, proposed monetary hard-stop rules, quota defaults, billing controls and cost-abuse test plan.
11. Raspberry Pi 5 ARM64 hosting feasibility, secure inbound access approach, production Compose topology, resource/storage assessment, GH Actions CI/CD design, release/rollback/backup drills and home-network threat model.

**Stop for approval.**

### Phase 1 — Secure foundation and content workflow

Build in separately approved small slices:
- 1A: repository tooling, CI, DB and test infrastructure, secure configuration; ARM64 image build verification and a separate non-production Compose smoke test.
- 1B: verified ChatGPT-only sign-in feasibility/integration, login/logout, local app session/CSRF, authorization tests. If official identity access is blocked, stop and request a product decision; do not substitute a different provider automatically.
- 1C: projects/modules/topics/items CRUD with strict user ownership.
- 1D: JSON schema/template, validation, preview, safe ADD_NEW_ONLY import, concurrency/idempotency, content export.
- 1E: responsive PWA project dashboard and content navigation.

### Phase 2 — Learning practice and FSRS

- 2A: reading, listening/TTS, writing.
- 2B: read aloud, fill-gaps, keyword speaking, free speaking and safe browser audio capture.
- 2C: review scheduling, per-item review history, due queue and progress.

### Phase 3 — Enhanced speech and assessment (NOT MVP)

- Free-first STT provider adapters and optional on-device Whisper; gated paid OpenAI speech STT/TTS with budget reservation and quotas; transcript correction, privacy-controlled audio storage, AI feedback separately enabled only when verified delegated ChatGPT authorization is available, language-versus-technical evaluation, follow-up challenges.

### Phase 4 — Future evolution (defer)

- More content types and scenarios, job-description-driven study plans, sophisticated personalized exercises, verified offline syncing, native app if usage justifies it, collaborative learning only with a new permissions model.

**After each numbered subphase, stop and wait for approval.** An approved phase does not imply authorization to implement all its subphases.

## 12. Output format after every completed slice (Turkish conversation)

1. **Delivered scope** and what changed.
2. **Design decisions** and why they are MVP-appropriate.
3. **Tests**: exact commands and actual results, plus Red/Green/Refactor evidence.
4. **Security Reviewer**: scope, control mapping, findings/severity, resolution, residual risks.
5. **Manual verification steps** for the user.
6. **Risks / deferred items** and documentation updates.
7. **Next smallest proposed slice**, awaiting explicit approval.

At the end of the project, generate concise, project-factual technical interview preparation notes under `docs/interview/` and add `/docs/interview/` to `.gitignore` from the beginning. These notes are local/private, must never be committed, and must not include private user data. Cover architecture decisions, trade-offs, real problems encountered, tests/security evidence and truthful STAR stories. Do not invent achievements.

## 12A. Mandatory deployment target: home Raspberry Pi 5 and secure delivery

**Confirmed product constraint:** Deploy the MVP publicly from the user's home **Raspberry Pi 5 (16 GB RAM)** running **Ubuntu Server 64-bit**. Do not assume a cloud managed database or a cloud VM. Preserve the existing modular monolith and all v1.1 identity, API spend, TDD and security requirements. Never publish or request the user's home IP, domain, tunnel token or other sensitive host details in repository documentation.

### Phase 0 environment inventory and feasibility gate

Before implementation, ask the user only for genuinely blocking host-specific decisions. Propose safe commands to inspect (do not claim you have run them): `uname -m` (`aarch64` expected), `lsb_release -a`, memory/storage/free disk, filesystem, Docker/Compose versions, boot media/SSD availability, router topology/CGNAT, domain/DNS control, backup destination, uptime/power/network constraints. Prefer a reliable SSD rather than a microSD card for write-heavy PostgreSQL data. Check official ARM64 container image support (including dependencies) and hosting restrictions/ISP terms. Establish actual resource ceilings and avoid AI model inference on the Pi unless benchmarked; keep paid inference gated and cloud providers independent.

### Runtime layout and networking

- **Single machine:** production `compose.yaml` with separate `web` (static built PWA served by minimal web server/reverse proxy), `api` (FastAPI modular monolith), `db` (PostgreSQL), and only necessary `ingress`/tunnel components. Dedicated private network, persistent named volumes or explicit secure mounts, restrictive file permissions. No Redis, K8s, Kafka, Celery or heavy monitoring stack by default.
- **Exposure:** expose only public HTTPS web entrypoint. **Never publish PostgreSQL, admin/debug endpoints, Docker daemon, SSH or internal FastAPI service to the public internet.** Configure PostgreSQL container as internal-only (`expose` or private-network connectivity rather than published host ports). Restrict management to a secure private channel such as Tailscale/WireGuard, not public SSH.
- **Preferred public ingress to evaluate:** outbound-only **Cloudflare Tunnel** when a domain and its usage/privacy terms are acceptable; no router port forwarding or fixed public IP needed. Compare briefly with direct Caddy TLS reverse proxy/port forwarding (only if the user knowingly chooses it). Tunnel is not a replacement for the application's login/authorization, request validation or origin hardening. Protect origin reachability, validate trusted proxy/forwarded headers, enforce HTTPS external scheme, secure cookies, correct OAuth redirect URLs and CORS/CSRF. Do not blindly trust arbitrary `X-Forwarded-*` headers. OAuth identity feasibility is still a hard gate.
- **Docker security:** official supported Ubuntu ARM64 Docker installation; explicitly account for Docker port publishing bypassing naive `ufw` policies. Only bind necessary host ports to loopback or isolated networks, use Docker/network firewall rules where relevant, no `privileged`, no host networking or docker.sock mounts in app containers; non-root users, read-only root filesystems where feasible, drop unnecessary Linux capabilities, `no-new-privileges`, resource limits, health checks and restart policies. Pin base images to maintained versions/digests after verification; avoid `latest` in production.
- **Secrets:** never bundle production credentials, tunnel credentials, OpenAI API keys, cookies or SSH keys in images/repository, GitHub build artifacts or front-end. Prefer permissions-restricted host-side secret files / Docker secrets where feasible and document rotation. Protect backups and all access tokens.
- **Reliability:** restart on reboot; health/readiness endpoints that disclose no secrets; CPU/RAM/disk usage monitoring, bounded JSON logs with retention, no raw user audio or access tokens in logs; configure timestamp/timezone/clock sync; storage pressure alerts; power outage behavior; optional UPS based on actual risk.
- **Data and privacy:** minimal audio retention, volume encryption at rest where practical and documented, retention policy, GDPR/KVKK applicability review for public users, no public exposure of personal learning data.

### Secure CI/CD architecture — build away from the home server

1. **GitHub repository** with protected `main` branch, required successful CI checks, reviewed production environment, explicit manual production deployment approval for MVP. Never auto-deploy unreviewed pull requests or fork-origin contributions to a home server.
2. **CI on GitHub-hosted runners** (not a permanently running self-hosted runner on the Raspberry Pi): run backend/frontend lint, formatting, static types, unit/integration tests, negative authorization and JSON import tests, minimal Playwright smoke tests, secret scanning, dependency/vulnerability scans, container/Dockerfile scanning and workflow misconfiguration checks. Fail on critical/high actionable findings; risk-based exceptions must be documented and approved. Apply least-privilege `GITHUB_TOKEN` permissions; pin Actions through lockfiles or audited full-length SHAs; do not expose secrets to untrusted PR jobs. Use lockfiles, dependency hashes/pinning where appropriate.
3. **Build ARM64 production images** using Buildx on GitHub-hosted runner (`linux/arm64`, optional AMD64 images for development). Prefer native GitHub-hosted ARM64 runner if repo/plan supports it, otherwise verified QEMU build; make no assumption about availability. Ensure native dependencies for Python/audio are compatible. Push immutable **SHA/digest-tagged** images to an authenticated registry such as GHCR. Container registry permissions: build has package publish, production deployment has read-only pull; no release from uncontrolled mutable tags. Record image provenance/SBOM when practical.
4. **CD approval and delivery:** initial deployment approach: GitHub Actions builds, tests, publishes **only**; the Raspberry Pi **pulls** approved immutable release digests through a minimal, tightly scoped deployment process initiated by a trusted administrator over private VPN/SSH, or by a host-side puller restricted to an explicit signed/approved release manifest. Avoid an inbound deployment webhook, inbound SSH from GitHub Actions, GitHub-hosted runners holding unrestricted Pi admin SSH keys, or permanent GitHub Actions self-hosted runners on the home machine. If automated pull-based rollout is later needed, threat-model and approval-gate it before coding; no silent auto-upgrade to newest tag.
5. **Release sequence:** verify approved image digest, ensure fresh restorable off-device backup, check free disk, pull exact digests, check compatible forward-only Alembic migrations with migration policy/backup, controlled Compose update, readiness+smoke tests, record deployed SHA; if unhealthy, restore previous image version where migration compatibility permits. **Database rollback is not always reversible**: prepare expand/contract migrations and documented restore procedure rather than claiming instant rollback.
6. **Production change control:** restrict environment approvals to authorized maintainers, concurrency guard for one deployment at a time, immutable artifact promotion, no production secrets in CI build context, audit releases and protect workflow modifications/code owners where practical. Deploy scripts must be idempotent, fail closed, and reject unapproved images.
7. **Off-device encrypted backups:** scheduled PostgreSQL logical backups, application persistent data/audio if retained, necessary configuration and recovery metadata; store at a separate trusted location not only on the Pi, encrypt, restrict access, rotate, verify integrity, test full restore into isolated environment. Define RPO/RTO targets and cleanup of old volumes/images without deleting recent backups. No secrets in unencrypted backups.
8. **Observability:** uptime/health monitoring from outside the home network, structured redacted security logs, actionable disk/memory/temperature/DB-health alerts, simple metrics first. Investigate abuse, request-cost protection and API quotas independently of deployment health.

### Separate deployment safety acceptance tests

- ARM64 images start on Pi or a representative ARM64 environment; `/health/live` and `/health/ready` behave correctly, DB migrations work; services recover after reboot.
- No published host port for DB, API admin or management surface; external scans and Compose config confirm isolation, including Docker firewall/ufw interaction.
- Public HTTPS + valid certificate, OAuth callback proxy headers/cookies/CSRF confirmed, no user BOLA bypass through proxy routing.
- Untrusted PR cannot access production deployment credentials or trigger deployment; workflow permissions are audited.
- Image deploy by digest with approved release; tampered/unsigned/unapproved release rejected.
- Migration failure preserves data and triggers stop; verified snapshot and rehearsed restore; image rollback handles schema compatibility correctly.
- Internet outage, tunnel failure, low disk, host reboot, exhausted memory, concurrent deployment and kill-switch behavior tested/documented to the extent practical.
- OpenAI paid speech defaults disabled; quotas, reservation and global kill switch remain effective behind the public ingress; no secret leak in logs, registry or image layers.
- No claim of zero downtime or production-grade HA on a single home Pi; explicitly document single points of failure and residential ISP/power limitations.

### Phase refinement (do not bypass approval gate)

- **Phase 0:** propose and approve network/deploy threat model, Pi resource/SSD/backups baseline and CI/CD pipeline design, with diagrams and ADRs. No application code yet.
- **Phase 1A:** set up secure CI/test workflow and reproducible ARM64 image build in addition to repository scaffolding. Validate Compose locally without putting server online.
- **Phase 1B–1E:** implement app/security/data slices as already specified; local/staging tests throughout.
- **Dedicated production-release subphase after foundation:** harden Pi, choose/configure ingress, provision secrets, encrypted off-device backups, release pipeline, health monitoring and restoration exercises. **Require explicit separate approval for any publicly accessible deployment.**
- Later phases inherit same CI/CD, image supply-chain gates and threat models.

### Sources to verify in Phase 0 (official)

- Docker Ubuntu install/ARM64/firewall caveats: https://docs.docker.com/engine/install/ubuntu/
- GitHub-hosted runner architectures: https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job
- GitHub Actions secure use: https://docs.github.com/en/actions/reference/security/secure-use
- Cloudflare Tunnel architecture and public origin exposure: https://developers.cloudflare.com/tunnel/
- Cloudflare Tunnel setup and domain prerequisite: https://developers.cloudflare.com/tunnel/get-started/

---

## 12B. Explicit GitHub Actions workflow requirements

- Create separate `ci.yml` and manually approved `release.yml` as the simple baseline; avoid a large reusable-workflow framework for the MVP. No Jenkins controller, plugins or `Jenkinsfile` required.
- `ci.yml` must run for PRs and protected `main`: formatting, lint, Python/TypeScript type checks, unit/integration/security tests, SQL migration checks, secret detection, dependency checks, Docker/Compose and workflow checks. Require successful CI in branch protection.
- Restrict workflow-level `permissions` to read-only by default. The release job may receive tightly scoped package-write access only for GHCR publication. Pin external actions to audited full-length commit SHAs, prefer immutable dependencies and review changes to workflows.
- Untrusted PR workflows must not receive secrets or deployment credentials. Avoid `pull_request_target` checkout of untrusted code. Add job concurrency guards for releases.
- Build `linux/arm64` images off the production Raspberry Pi and publish digest-addressable images to GHCR. Validate the architecture and provenance; optionally add SBOM and image vulnerability scans if proportionate to MVP.
- The production Raspberry Pi must never execute source scripts fetched ad hoc from an unreviewed branch. Approved release metadata includes commit SHA and immutable image digests. Deployment script verifies approvals and refuses unknown digests.
- Separate image rollback from DB rollback; use reversible/expand-contract schema changes where possible, backups before high-risk migrations and tested restore procedures. Never assume downgrade is safe.
- Deliver a sanitized operator runbook with initial provisioning, SSH/VPN or pull-release commands, rotation of secrets, backup restore, health verification, emergency paid-API shutdown, and incident response. Production secrets remain outside the repository and CI build contexts.

## 13. Start now

**Do Phase 0 only. Treat this as a potentially PUBLIC GitHub repository and include a public-repo secret hygiene threat model, migration/seed secret policy, scanning gates, and credential rotation process. In particular, research and clearly report whether official Sign in with ChatGPT and delegated usage integrations are actually available to this hosted PWA; no undocumented workaround is acceptable. Add a dedicated API-spend-abuse threat model and hard-stop controls. Validate Raspberry Pi 5 / Ubuntu ARM64 hosting and propose secure GitHub Actions CI/CD with explicit release approval, rollback and off-device backups.** Review this specification, inspect the available project directory, verify practical technical choices and security controls, produce architecture/threat-model/phase plan for my review, and STOP. Do not scaffold or implement until I explicitly approve the first implementation subphase. Communicate with me in Turkish; write all project artifacts and technical specifications in English.

---

### Authoritative security references (official)

- OWASP ASVS: https://asvs.owasp.org/ (stable 5.0.0 at specification time)
- OWASP API Security Top 10: https://owasp.org/API-Security/editions/2023/en/0x00-header/
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- OWASP Cheat Sheet Series: https://cheatsheetseries.owasp.org/
- NIST SP 800-63B-4: https://pages.nist.gov/800-63-4/sp800-63b.html
- OWASP SAMM: https://owaspsamm.org/

### Official provider guidance on spend and identity

- OpenAI project spend limits and enforced hard limits: https://developers.openai.com/api/docs/guides/spend-limits
- OpenAI rate limits and individual user safeguards: https://developers.openai.com/api/docs/guides/rate-limits
- OpenAI projects, model access, spend alerts: https://help.openai.com/en/articles/9186755-managing-projects-in-the-api-platform
- Sign in with ChatGPT identity and separate subscription-sharing permission: https://help.openai.com/en/articles/20001410-sign-in-with-chatgpt
