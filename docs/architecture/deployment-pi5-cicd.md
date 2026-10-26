# Raspberry Pi 5 Hosting and GitHub Actions CI/CD

Status: PROPOSAL. Host inspection NOT yet performed; the commands below are for the owner to run.

## Host inventory (owner to run, paste output with no secrets)

```bash
uname -m; lsb_release -a; free -h; df -h; lsblk -f
docker --version; docker compose version
vcgencmd measure_temp; timedatectl
```
Also needed: SSD or microSD, router/CGNAT status, domain and DNS provider, backup destination, UPS.

## Feasibility (from spec, unverified on hardware)
16 GB RAM is ample for FastAPI + PostgreSQL + static server + tunnel. PostgreSQL must live on an SSD. Python, Node and Postgres images support ARM64; confirm each dependency at build. No AI inference on the Pi.

## Ingress comparison
| Option | Pros | Cons |
|---|---|---|
| Cloudflare Tunnel (recommended) | Outbound only, no port forwarding, works behind CGNAT, hides home IP | Needs a domain on Cloudflare; traffic terminates at Cloudflare; third-party dependency |
| Caddy + port forward | No third party | Exposes home IP and ports; fails behind CGNAT |

Official docs to confirm before 1F: Docker Ubuntu install, GitHub runner architectures, GitHub secure-use, Cloudflare Tunnel (links in the master prompt).

## Production Compose topology
Services: `web` (static PWA), `api`, `db`, `cloudflared`. One private network; only `cloudflared` reaches `web`; no host ports published except loopback if needed. Hardening on every container: non-root, `read_only`, `cap_drop: [ALL]`, `no-new-privileges`, memory/CPU limits, healthchecks, `restart: unless-stopped`, digest-pinned images, `secrets:` from root-owned files outside the checkout. No privileged, host network or docker.sock. Docker bypasses ufw for published ports; verify with `DOCKER-USER` rules and an external scan.

## CI/CD
- `ci.yml` (PR + main): ruff, mypy, pytest (unit, integration with PostgreSQL service, authz, security), alembic checks, ESLint/tsc/Vitest, Playwright smoke, gitleaks, pip-audit, npm audit, Trivy fs and image, hadolint, `docker compose config`, actionlint and zizmor. `permissions: contents: read`; actions pinned to full SHAs; no `pull_request_target`; no secrets on PR jobs.
- `release.yml`: manual `workflow_dispatch` on `main`, `environment: production` with required reviewer, concurrency group, `packages: write` only. Builds `linux/arm64` (native ARM runner if available, otherwise QEMU; availability unverified), pushes to GHCR by digest, emits SBOM and provenance, writes a release manifest (commit SHA + digests).
- Deploy: pull-based. Over WireGuard/Tailscale the admin runs a small script on the Pi that accepts only digests listed in the approved manifest, checks fresh backup and disk space, runs forward-only Alembic, applies Compose, smoke-tests, records the SHA. No inbound webhook, no GitHub-held SSH key, no self-hosted runner.
- Rollback: image rollback is a Compose digest revert. DB rollback uses expand/contract migrations plus restore from backup; no downgrade is assumed safe.

## Backups
Nightly `pg_dump` encrypted with `age` and sent off-device (destination: D-4). Proposed RPO 24 h, RTO 4 h. Quarterly restore drill into an isolated environment. Retention 7 daily / 4 weekly / 6 monthly.

## Acceptance tests
As listed in spec 12A: ARM64 boot, no published DB port (external scan), fork PR has no secrets, tampered or unlisted digest rejected, failed migration stops with data intact, reboot recovery, low-disk and tunnel-down behavior documented. Single-Pi downtime is accepted and documented.
