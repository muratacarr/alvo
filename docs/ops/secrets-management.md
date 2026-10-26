# Secrets Management

No values appear in this file. The repository is treated as public.

## Rules
- Real secrets never enter Git, images, build args, `VITE_*` variables, CI artifacts or logs.
- `.env.example` holds placeholders only; the application refuses to start with them (`alvo.shared.config.Settings`).
- Production secrets are injected at runtime from root-owned, permission-restricted files outside the checkout.
- Development, CI and production use separate credentials.

## Local setup
1. Copy `.env.example` to `.env` (ignored by Git) and set real local-only values.
2. Install the scanner: `winget install Gitleaks.Gitleaks` (Windows) and run `uv run --project apps/api pre-commit install`.

Production secrets, the tunnel token and the backup key are described in `production-runbook.md`.

## Rotation (outline; expanded in the production-release subphase)
Rotate the session secret (invalidates sessions), database password, OpenAI key, tunnel credential and backup key on a schedule and after any suspected exposure.

## Leak response
1. Revoke and rotate the credential immediately. Deleting the commit is not enough.
2. Identify exposure window and access in provider logs.
3. Remove from history only after rotation (approved procedure), force-push, and ask GitHub support to purge caches if the repo was public.
4. Record a sanitized incident note; keep exploitable details out of the public repo.
5. Run a drill before the first public release.
