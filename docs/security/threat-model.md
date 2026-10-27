# Alvo Threat Model (Phase 0)

Scope: web PWA, API, PostgreSQL, GitHub repo and CI, GHCR, Raspberry Pi 5 host, tunnel. Status: PROPOSAL.

## Assets
User accounts and sessions; learning content and answers (personal data); optional recordings; owner's OpenAI key and budget; GitHub and GHCR credentials; tunnel credential; backup keys; the Pi and home network.

## Trust boundaries
Browser <-> edge; edge <-> tunnel <-> origin; web <-> api; api <-> db; GitHub (public) <-> maintainers; CI <-> GHCR; GHCR <-> Pi; Pi <-> home LAN; api <-> third-party providers.

## Threats and controls

| # | Threat | Control | Residual |
|---|---|---|---|
| T1 | BOLA/IDOR across users | Server-derived owner, composite FKs, deny-by-default `ProjectAccess`, two-user tests on every endpoint, 404 for foreign ids | low |
| T2 | Session theft / fixation / CSRF | Opaque hashed server sessions, `__Host-` cookie, rotation, Origin+token CSRF, no tokens in localStorage | XSS on same origin |
| T3 | XSS via imported content | Render as text only, no raw HTML, strict CSP (no inline script), JSON Schema bounds | medium until e2e XSS tests exist |
| T4 | Malicious/oversized import (resource exhaustion, nested JSON, duplicate keys) | Caps, streaming body limit, atomic transaction, timeouts, per-user rate limits | low |
| T5 | Brute force / abuse of auth endpoints | Rate limits at nginx and in the API (ADR 0009), provider-delegated auth (no passwords) | credential stuffing not applicable |
| T6 | Injection | ORM parameters only, no dynamic SQL, ruff/bandit rules | low |
| T7 | Secret leakage in public repo, history, CI logs, images | Gitleaks pre-commit + CI full-history, push protection, runtime placeholder rejection, no `ARG/ENV` secrets, image-layer scan | human error before scanner |
| T8 | Supply chain (deps, actions, base images) | Lockfiles with hashes, Dependabot, SHA-pinned actions, digest-pinned base images, pip-audit/npm audit/Trivy, SBOM | zero-day |
| T9 | Malicious PR / workflow injection | No `pull_request_target`, no secrets on PR jobs, read-only token, CODEOWNERS on workflows, zizmor | low |
| T10 | Compromised CI or registry pushes bad image | Digest-only deploy, owner-approved release manifest, Pi pull-based, no CI credentials to Pi | owner approves a bad digest |
| T11 | Exposed DB/Docker/SSH on home network | No published DB port, no docker.sock mounts, management over WireGuard/Tailscale only, nftables/DOCKER-USER rules | Docker/ufw bypass needs verification on the Pi |
| T12 | Forged forwarded headers | Trust only tunnel network, enforce scheme | low |
| T13 | Data loss (SD wear, power cut, ransomware) | SSD, encrypted off-device backups, restore drills, RPO 24 h / RTO 4 h (proposed) | single Pi is a single point of failure |
| T14 | Personal data/privacy (GDPR/KVKK) | Minimal data, deletion path, short audio retention, no content in logs | legal review needed before public users |
| T15 | Prompt injection / unsafe AI output | Imported text is data; AI features disabled in MVP | n/a until Phase 3 |
| T16 | Paid API cost abuse | See `ai-spend-threat-model.md` | provider billing lag |
| T17 | Learner text processed by a third-country LLM provider (DeepSeek) | Consent and disclosure, minimization, no PII in prompts, per-user admin grant, provider can be disabled by the kill switch | Provider-side retention and legal access are outside our control |

## Public repository & secrets (summary of spec 0B)
Controls: Gitleaks (pre-commit and CI full history), GitHub secret scanning + push protection (confirm plan coverage), migration/fixture credential tests, startup validator rejecting placeholders, `.env.example` placeholders only, secrets injected at runtime from root-owned files outside checkout. Leak response: revoke and rotate first, investigate, then history scrub if needed; runbook and drill in `docs/ops/secrets-management.md` (Phase 1A). Public-release gate audit before first public push. Until then the repo must stay local/private.

## Security Reviewer process
Every change runs `docs/security/review-checklist.md` (to be created in 1A-1) and a Claude Code review subagent if available. Critical/High block; Medium need fix or owner-approved, time-boxed exception.
