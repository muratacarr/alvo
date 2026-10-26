# API Spend Policy

1. One guarded gateway (`BudgetGuard`) is the only code allowed to import a paid provider SDK. Enforced by an import-linter contract.
2. Flow: authorize -> estimate worst case -> atomic reserve (user and global) -> call -> settle -> release remainder.
3. Defaults: every paid flag false, every cap 0. Changes are audited admin operations.
4. Failure of ledger, pricing, entitlement store or kill-switch store means deny.
5. CI, tests and local development use mocked providers; real-spend tests need an explicit manual opt-in.
6. Alerts at 50/75/90% of the app cap (provider alerts are not limits).
7. Owner-only manual checks (cannot be done by the assistant): dedicated OpenAI project, project hard limit, restricted key, auto-recharge off or bounded.
8. Error codes: `PAID_FEATURE_DISABLED`, `PAID_ACCESS_DENIED`, `USER_QUOTA_EXCEEDED`, `GLOBAL_BUDGET_EXCEEDED`, `BUDGET_GUARD_UNAVAILABLE`, `PROVIDER_LIMIT_REACHED`.
