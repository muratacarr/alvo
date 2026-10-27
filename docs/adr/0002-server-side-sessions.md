# ADR 0002: Server-side opaque sessions with Origin and CSRF checks

Status: Accepted (slice 1B-1)

## Context
Alvo is a same-origin PWA and API behind one host. It needs revocable logins, protection against session theft from a database leak, and protection against cross-site request forgery. Bearer tokens in `localStorage` are exposed to any XSS.

## Decision
- The browser holds a random 256-bit token in the cookie `__Host-alvo_session` (`HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, no `Domain`).
- The database stores only `HMAC-SHA256(session_secret, "session:" + token)`. A database leak alone cannot be replayed as a session; rotating `session_secret` invalidates all sessions.
- Idle timeout 30 min (sliding, refreshed at most once a minute) and absolute lifetime 12 h, both configurable.
- Sign-in always issues a fresh token and revokes any presented one (anti-fixation). Logout revokes server-side.
- Unsafe methods require an exact `Origin` match with `public_origin`. Authenticated unsafe requests also need `X-CSRF-Token`, a stateless `HMAC(session_secret, "csrf:" + session_hash)` bound to that session.
- CORS stays disabled (same origin).
- A development-only login (`/api/v1/auth/dev-login`) exists only when `identity_provider=mock` and `environment != production`. `Settings` refuses to start in production with the mock provider or a non-https `public_origin`.
- Sign-in is provider-agnostic: any provider only has to yield a `VerifiedIdentity(provider, subject)`.

## Consequences
- No horizontal scaling concerns for sessions (PostgreSQL is shared), at the cost of one query per authenticated request.
- Sign-in requests are rate limited per client address and signed-in users per minute (ADR 0009); the mock route is unreachable in production.
- `Origin` is required, so non-browser API clients must send it.
