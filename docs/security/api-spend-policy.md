# API Spend Policy

1. One guarded gateway (`BudgetGuard`) is the only code allowed to import a paid provider SDK. Enforced by an import-linter contract.
2. Flow: authorize -> estimate worst case -> atomic reserve (user and global) -> call -> settle -> release remainder.
3. Defaults: every paid flag false, every cap 0. Changes are audited admin operations.
4. Failure of ledger, pricing, entitlement store or kill-switch store means deny.
5. CI, tests and local development use mocked providers; real-spend tests need an explicit manual opt-in.
6. Alerts at 50/75/90% of the app cap (provider alerts are not limits).
7. Owner-only manual checks (cannot be done by the assistant): dedicated OpenAI project, project hard limit, restricted key, auto-recharge off or bounded.
8. Error codes: `PAID_FEATURE_DISABLED`, `PAID_ACCESS_DENIED`, `USER_QUOTA_EXCEEDED`, `GLOBAL_BUDGET_EXCEEDED`, `BUDGET_GUARD_UNAVAILABLE`, `PROVIDER_LIMIT_REACHED`.

## Providers and entitlements (ADR 0004)
9. Paid providers: DeepSeek (text generation) and OpenAI (speech). Each has its own server-side key, model allowlist, circuit breaker and entry in the ledger. Keys never reach the browser, logs or images.
10. A new user holds no entitlement. Only an admin can grant per-feature access; grants and limit changes are audited and need recent re-authentication. The first admin is created by a host-side command.
11. `exempt` removes per-user quotas only. Per-request size limits, global budget, global concurrency, kill switch and provider hard limits still apply to everyone.
12. Text sent to DeepSeek is minimized (no names, emails or unrelated user data) and requires an explicit, recorded user consent because it is processed outside the EU/Turkey (see ADR 0004, D-8).
