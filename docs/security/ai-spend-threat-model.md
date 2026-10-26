# AI Spend Abuse Threat Model

Status: PROPOSAL. Phase 3 only; no paid call exists before then. No prices are stated here: the pricing catalog must be filled from official OpenAI pricing at implementation time.

## Abuse cases and controls

| Case | Control |
|---|---|
| Stolen session triggers paid calls | Paid features need per-user admin entitlement plus fresh explicit intent per call; per-user daily/monthly caps bound loss to one user's allowance |
| Malicious authorized user | Per-user USD, duration, character, rate, concurrency caps; anomaly alert |
| Replay / retry storm | Idempotency key with unique constraint and TTL; no duplicate settlement |
| Concurrency race on last allowance | Reservation via row lock / conditional UPDATE; test with 20 parallel requests |
| Broken or stale price catalog | Fail closed when price missing or older than policy |
| Provider outage / timeout | `uncertain` reservation kept, bounded retries, reconcile before release |
| Admin account compromise | Re-authentication for grants, audit log, global cap and kill switch independent of admin UI (env/DB flag) |
| Fake audio duration / MIME | Server measures actual bytes and decoded duration before upload |
| Browser STT failure | Never auto-falls back to paid |
| Client-chosen model | Models fixed server-side by allowlist |

## Worst-case loss
Bounded by min(app global monthly cap, provider project hard limit). The app cap is set below the provider limit with a margin because provider enforcement can lag. Concrete values are an owner decision (D-5) and are not invented here.

## Proposed defaults (all disabled)
`PAID_AI_ENABLED=false`, all per-feature flags false for every user, global and per-user caps = 0 until the owner sets them. Rationale: zero spend unless deliberately configured.

## Release gate
No paid adapter until: the 10 cost-security tests pass, admin entitlements exist, the provider hard limit is verified manually by the owner with redacted evidence, kill switch exercised, owner approves the slice.
