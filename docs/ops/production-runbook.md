# Production runbook (Raspberry Pi 5)

Status: **slice 1F-1.** The production stack definition and the backup tooling exist and are tested. The stack cannot serve real users yet; see "Not done yet" at the end. Nothing in this file contains a secret.

## What exists

| Piece | File |
|---|---|
| Production stack (db, api, web, cloudflared) | `compose.prod.yaml` |
| Encrypted off-device backup | `ops/backup/backup.sh` |
| Restore drill (proves a backup works) | `ops/backup/restore-drill.sh` |

The production file differs from the development one on purpose: images by digest only, no published ports (the only way in is the outbound Cloudflare Tunnel), secrets from root-owned files outside the checkout, no internet route for the API or database, no development sign-in. `apps/api/tests/security/test_compose_prod_policy.py` enforces all of it.

## 1. Prepare the Pi (owner)

Run these and keep the output for the next slice (no secrets in it):

```
uname -m; lsb_release -a; free -h; df -h; lsblk -f
docker --version; docker compose version
```

- The database must live on an **SSD**, not a microSD card. Point Docker's data directory at the SSD (`data-root` in `/etc/docker/daemon.json`) before the first start.
- Install Docker from Docker's official apt repository, and the host tools used by the backup: `age` and `rclone`.
- Enable automatic security updates and a host firewall. Docker bypasses `ufw` for published ports; this stack publishes none, which is the real protection.

## 2. Secrets (owner, on the Pi)

Secrets live in `/etc/alvo/secrets`, readable only by root; the directory, not the file mode, keeps other users out (containers run as other uids and read the bind-mounted files).

```
sudo install -d -m 700 /etc/alvo/secrets
cd /etc/alvo/secrets
sudo sh -c 'umask 022; openssl rand -base64 24 | tr -d "\n=+/" > db_password'
sudo sh -c 'umask 022; openssl rand -base64 48 | tr -d "\n" > alvo_session_secret'
# alvo_database_url must contain the same password as db_password:
#   postgresql+psycopg://alvo_app:<db_password>@db:5432/alvo
# Create it with an editor, not with a command that puts the password into your shell history.
# tunnel_token: the token from the Cloudflare dashboard (step 3).
```

Never paste these values into chat, issues, CI or a commit. Rotate them if they are ever exposed (see `secrets-management.md`).

## 3. Cloudflare Tunnel (owner)

1. Put the domain on Cloudflare (DNS managed there).
2. Zero Trust dashboard, Networks, Tunnels: create a tunnel, choose the Docker connector, and copy only the **token** into `/etc/alvo/secrets/tunnel_token`.
3. Add a public hostname (for example `alvo.<your-domain>`) with service type HTTP and URL `http://web:8080`.
4. Set `ALVO_PUBLIC_ORIGIN=https://alvo.<your-domain>`. The API refuses to start in production with an `http://` origin.

Traffic terminates at Cloudflare; this is the accepted trade-off for not opening any port at home (decision D-3).

## 4. Starting the stack

Needs the approved image digests from the release manifest (produced by the release workflow, a later slice):

```
export ALVO_PUBLIC_ORIGIN=https://alvo.<your-domain>
export ALVO_API_DIGEST=sha256:<from the release manifest>
export ALVO_WEB_DIGEST=sha256:<from the release manifest>
docker compose -f compose.prod.yaml config -q      # fails if anything required is missing
docker compose -f compose.prod.yaml up -d
docker compose -f compose.prod.yaml run --rm api alembic upgrade head
docker compose -f compose.prod.yaml ps             # every service should become healthy
```

`cloudflared` shows `unhealthy` while the tunnel is not connected.

## 5. Backups

**How it works:** `pg_dump` is encrypted with the **public** age key and uploaded with rclone. The Pi never holds the private key, so someone who steals the Pi cannot decrypt old backups from the bucket.

One-time setup (owner):

1. On your own computer: `age-keygen -o alvo-backup.key`. Keep this file offline (password manager and a second offline copy). Losing it means losing every backup. Copy only the printed public key (`age1...`) to the Pi.
2. Create a bucket at your object-storage provider and an **application key limited to that bucket** (write and list; no delete if the provider allows it). Configure it on the Pi with `rclone config` (root's config file, mode 600).
3. Set a lifecycle rule on the bucket for retention (target: 7 daily, 4 weekly, 6 monthly; at least keep 35 days). Enabling Object Lock or versioning protects against a compromised Pi deleting backups.
4. Schedule it (systemd timer or cron, as root):

```
ALVO_BACKUP_AGE_RECIPIENT=age1... \
ALVO_BACKUP_REMOTE=alvo-backups:<bucket>/db \
/opt/alvo/ops/backup/backup.sh
```

The script refuses a suspiciously small dump, uploads nothing on failure, and records `/var/lib/alvo-backup/last-success` (the deploy step in the next slice will refuse to deploy without a fresh backup).

**Restore drill (do it before launch, then every quarter).** Never practise on production. Use a scratch stack, for example the development stack on your computer:

```
# download one backup file from the bucket, then:
ALVO_BACKUP_AGE_IDENTITY=/path/to/alvo-backup.key \
  ops/backup/restore-drill.sh alvo-20260101T020000Z.dump.age
```

It restores into a temporary database, prints the table count and schema version, then drops it. A backup that has never been restored is not a backup.

Targets: RPO 24 hours (nightly), RTO 4 hours.

### What was verified, and how

On 2026-10-26 the real chain (real `pg_dump`, real `age`, real `pg_restore`) was run against the development database: the encrypted file started with the age header and contained no plaintext, the drill restored 10 tables at schema version 0005, a wrong key failed cleanly, and the live database was untouched. The upload step was replaced by a copy to a local folder, so **rclone against a real bucket has not been tested**. Do that during step 5.2.

## Not done yet (do not tell anyone the system is production-ready)

- **Real sign-in method.** In production nobody can sign in (the development login is forbidden there). Decision D-1 is still open.
- **Release workflow and deploy script** (build ARM64 images, publish by digest, SBOM and provenance, pull-based deploy with backup and disk checks): slice 1F-2.
- **General and sign-in rate limiting** at the edge and in the API: slice 1F-3.
- **Host facts** (D-6) and the first real start on the Pi, including an external port scan, reboot test, low-disk and tunnel-down behaviour.
- **Provider calls and spend control** (BudgetGuard): Phase 3.
