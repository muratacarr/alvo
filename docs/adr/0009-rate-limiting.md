# ADR 0009: Rate limiting at the edge and in the API, counted in PostgreSQL

Status: Proposed, slice 1F-3 (awaiting owner review). Implements the rate-limiting line of `docs/architecture/phase-0-architecture.md` section 7.

## Context
The site is public behind a Cloudflare Tunnel on one Raspberry Pi. Nobody can sign in yet, but the API will gain a real sign-in method and paid AI features, and a small machine is easy to exhaust. Rate limits must be correct for this topology: one instance, no Redis, and every connection reaches us through the tunnel, so the socket peer is never the real client.

## Decision
1. **Two layers.** nginx (the only thing the tunnel talks to) drops floods early; the API enforces limits that need to know who the user is. Neither replaces the other.
2. **Edge (nginx).** Per client address: 20 requests per second with a burst of 40 for `/api/`, a stricter 10 per minute (burst 5) for `POST` under `/api/v1/auth/`, and 30 concurrent connections. Excess requests get `429` with the same body as the API, `{"error":"rate_limited"}`, and `Retry-After: 60`.
3. **Real client address.** nginx reads `CF-Connecting-IP`, trusted only when the connection comes from a private network (in production, only the tunnel, because nothing is published on the host). It then sets `X-Forwarded-For` to that address, overwriting rather than appending.
4. **API.** `ALVO_TRUST_FORWARDED_FOR` is off by default and on in both Compose files, because the API is reachable only through our nginx. The address is the last `X-Forwarded-For` entry if it parses as an IP, else the socket peer. Limits: `user_requests_per_minute` (default 300) per signed-in user on every authenticated route, and `auth_attempts_per_minute` (default 10) per client address on every unsafe `/api/v1/auth` request. The existing import-commit limit (30 per hour) stays.
5. **Counters in PostgreSQL**, fixed one-minute windows, one row per (bucket, window), incremented with a single atomic upsert in a short transaction of its own, so a request that later fails still counts. Rows older than two hours are deleted when a bucket opens a new window. Migration `0006`.
6. **Fail closed.** If the counter cannot be written the request fails with `500`, not unlimited access.

## Consequences
- Correct across restarts and several API workers, not across several database primaries or several sites; this is documented as a single-instance design.
- A fixed window allows up to twice the limit across a window boundary. Accepted: the goal is stopping abuse, not metering.
- Each authenticated request costs one extra small write. Acceptable at this scale; revisit if traffic grows.
- The numbers are conservative starting points (decision D-5 still open) and are settings, not code.
- Cloudflare's own rate limiting and bot protection (dashboard, outside this repository) can be added in front; this design does not depend on it.
- If a future change publishes the API or web port on the host, or lets another container reach the API, `trust_forwarded_for` and the `set_real_ip_from` ranges must be reconsidered; tests assert the current layout.
- Per-feature AI limits and spend caps are separate and arrive with Phase 3 (BudgetGuard).
