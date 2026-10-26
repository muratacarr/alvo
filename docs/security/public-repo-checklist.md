# Public Repository Checklist

Complete every item before the first public push. Status as of slice 1A-1:

- [x] `.gitignore` covers env files, keys, dumps, recordings, `/docs/interview/`
- [x] `.env.example` contains placeholders only and is proven not to boot the app (test)
- [x] Gitleaks configured; pre-commit blocks a fake credential and protected files (verified manually)
- [x] Gitleaks over full history defined in `ci.yml` (verified locally; not yet run on GitHub)
- [ ] GitHub secret scanning and push protection enabled (owner; plan coverage to confirm)
- [x] Actions pinned by full SHA, read-only token, no secrets in `ci.yml` (enforced by `test_workflow_policy.py`)
- [ ] Branch protection, required checks, Actions permissions restricted (owner, after the GitHub repo exists)
- [ ] Image layers and build contexts audited (1A-3)
- [ ] Leak-response drill performed
- [ ] Author identity in commits reviewed (the tooling left a personal email out of `pyproject.toml`; check `git config user.email` before the first commit)
