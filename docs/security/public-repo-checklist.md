# Public Repository Checklist

Complete every item before the first public push. Status after slice 1A-2. Items marked (owner) were configured in GitHub by the repository owner and not independently verified by tooling:

- [x] `.gitignore` covers env files, keys, dumps, recordings, `/docs/interview/`
- [x] `.env.example` contains placeholders only and is proven not to boot the app (test)
- [x] Gitleaks configured; pre-commit blocks a fake credential and protected files (verified manually)
- [x] Gitleaks over full history runs in `ci.yml` (first GitHub run green)
- [x] GitHub secret scanning (automatic on public repos) and push protection enabled (owner)
- [x] Actions pinned by full SHA, read-only token, no secrets in `ci.yml` (enforced by `test_workflow_policy.py`)
- [x] `main` ruleset: PR required, four CI checks required, force push and deletion blocked, no bypass (owner)
- [x] Actions permissions: read-only workflow token, approval for first-time fork contributors (owner)
- [x] Dependabot alerts and security updates enabled (owner)
- [ ] Image layers and build contexts audited (1A-3)
- [ ] Leak-response drill performed
- [x] Commit author identity uses the GitHub noreply address; command-line push email protection enabled (owner)
